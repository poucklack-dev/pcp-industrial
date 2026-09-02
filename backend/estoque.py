# backend/estoque.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, timedelta
from sqlalchemy import func, case
from backend.models import db, Produto, Movimentacao, Configuracao
from backend.auth import permissao_requerida, perfil_requerido

estoque_bp = Blueprint('estoque', __name__, url_prefix='/estoque')


def _numero(valor) -> float:
    """Converte saldos legados do SQLite para número antes de comparar."""
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalizar_estoques(produtos):
    for produto in produtos:
        produto.estoque_atual = _numero(produto.estoque_atual)
        produto.estoque_minimo = _numero(produto.estoque_minimo)
    return produtos


@estoque_bp.route('/')
@login_required
@permissao_requerida('ver_estoque')
def index():
    materias_primas = _normalizar_estoques(Produto.query.filter_by(tipo='MP').order_by(Produto.codigo).all())
    semi_acabados = _normalizar_estoques(Produto.query.filter_by(tipo='SA').order_by(Produto.codigo).all())
    produtos_acabados = _normalizar_estoques(Produto.query.filter_by(tipo='PA').order_by(Produto.codigo).all())
    movimentacoes = Movimentacao.query.order_by(Movimentacao.data_hora.desc()).limit(100).all()
    config = Configuracao.query.first()
    
    pode_editar = current_user.perfil in ['Analista', 'Supervisor']
    todos_produtos = materias_primas + semi_acabados + produtos_acabados
    total_criticos = sum(p.estoque_atual < p.estoque_minimo for p in todos_produtos)
    total_zerados = sum(p.estoque_atual <= 0 for p in todos_produtos)
    total_atencao = sum(
        p.estoque_atual >= p.estoque_minimo and p.estoque_atual < p.estoque_minimo * 1.5
        for p in todos_produtos if p.estoque_minimo > 0
    )
    inicio = date.today() - timedelta(days=6)
    movimentos_por_dia = {
        str(dia): {'entradas': 0, 'saidas': 0}
        for dia in (inicio + timedelta(days=indice) for indice in range(7))
    }
    for dia, entradas, saidas in Movimentacao.query.with_entities(
        func.date(Movimentacao.data_hora),
        func.sum(case((Movimentacao.quantidade > 0, 1), else_=0)),
        func.sum(case((Movimentacao.quantidade < 0, 1), else_=0)),
    ).filter(func.date(Movimentacao.data_hora) >= inicio).group_by(func.date(Movimentacao.data_hora)).all():
        if dia in movimentos_por_dia:
            movimentos_por_dia[dia] = {'entradas': int(entradas or 0), 'saidas': int(saidas or 0)}
    grafico_movimentacoes = {
        'labels': [(inicio + timedelta(days=indice)).strftime('%d/%m') for indice in range(7)],
        'entradas': [movimentos_por_dia[str(inicio + timedelta(days=indice))]['entradas'] for indice in range(7)],
        'saidas': [movimentos_por_dia[str(inicio + timedelta(days=indice))]['saidas'] for indice in range(7)],
    }
    
    return render_template(
        'estoque.html',
        materias_primas=materias_primas,
        semi_acabados=semi_acabados,
        produtos_acabados=produtos_acabados,
        movimentacoes=movimentacoes,
        config=config,
        pode_editar=pode_editar,
        todos_produtos=todos_produtos,
        total_criticos=total_criticos,
        total_zerados=total_zerados,
        total_atencao=total_atencao,
        grafico_movimentacoes=grafico_movimentacoes,
    )


@estoque_bp.route('/ajuste', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def ajuste():
    try:
        produto_id = int(request.form['produto_id'])
        quantidade = float(request.form['quantidade'])
        observacao = request.form.get('observacao', '')
        
        produto = Produto.query.get_or_404(produto_id)
        
        config = Configuracao.query.first()
        novo_estoque = _numero(produto.estoque_atual) + quantidade
        
        if novo_estoque < 0 and not config.permitir_estoque_negativo:
            flash('Estoque negativo não permitido! Ative a opção nas configurações.', 'danger')
            return redirect(url_for('estoque.index'))
        
        produto.estoque_atual = novo_estoque
        
        movimentacao = Movimentacao(
            produto_id=produto.id,
            quantidade=quantidade,
            tipo='Ajuste',
            usuario=current_user.nome,
            observacao=observacao or f'Ajuste de estoque: {quantidade} por {current_user.nome}'
        )
        db.session.add(movimentacao)
        db.session.commit()
        
        flash('Estoque ajustado com sucesso!', 'success')
    except ValueError:
        flash('Quantidade inválida!', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro no ajuste: {str(e)}', 'danger')
    
    return redirect(url_for('estoque.index'))


@estoque_bp.route('/configuracao', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def configuracao():
    try:
        config = Configuracao.query.first()
        if not config:
            config = Configuracao(permitir_estoque_negativo=False)
            db.session.add(config)
        
        permitir = bool(request.form.get('permitir'))
        config.permitir_estoque_negativo = permitir
        db.session.commit()
        
        flash('Configuração de estoque atualizada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar configuração: {str(e)}', 'danger')
    
    return redirect(url_for('estoque.index'))
