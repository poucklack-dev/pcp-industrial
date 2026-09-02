# backend/ordens.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_
from backend.models import db, Produto, OrdemProducao, Historico, Apontamento, Operador
from backend.auth import permissao_requerida
from backend.services import calcular_necessidades_recursivo, verificar_consumo

ordens_bp = Blueprint('ordens', __name__, url_prefix='/ordens')

TRANSICOES_STATUS = {
    'Planejada': {'Liberada', 'Cancelada'},
    'Liberada': {'Em produção', 'Cancelada', 'Bloqueada'},
    'Em produção': {'Pausada', 'Concluída', 'Cancelada'},
    'Pausada': {'Em produção', 'Cancelada'},
    'Bloqueada': {'Planejada', 'Cancelada'},
    'Concluída': set(),
    'Cancelada': set(),
}


@ordens_bp.context_processor
def utility_processor():
    return {'now': datetime.now()}


@ordens_bp.route('/')
@login_required
@permissao_requerida('ver_ordens')
def index():
    status = request.args.get('status', '')
    busca = request.args.get('busca', '').strip()
    prioridade = request.args.get('prioridade', '')
    produto_id = request.args.get('produto_id', type=int)
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    q = OrdemProducao.query
    if status:
        q = q.filter_by(status=status)
    if prioridade:
        q = q.filter_by(prioridade=prioridade)
    if produto_id:
        q = q.filter_by(produto_id=produto_id)
    if busca:
        q = q.join(Produto).filter(or_(
            OrdemProducao.numero.ilike(f'%{busca}%'), Produto.codigo.ilike(f'%{busca}%'), Produto.descricao.ilike(f'%{busca}%')
        ))
    try:
        if data_inicio:
            q = q.filter(OrdemProducao.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
        if data_fim:
            q = q.filter(OrdemProducao.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())
    except ValueError:
        flash('Período informado é inválido.', 'warning')
    ordens = q.order_by(OrdemProducao.data.desc(), OrdemProducao.id.desc()).all()
    situacao_material = {}
    for op in ordens:
        saldo = max((op.quantidade_planejada or 0) - (op.quantidade_produzida or 0), 0)
        if not op.produto.componentes:
            situacao_material[op.id] = 'Sem estrutura'
        elif not saldo:
            situacao_material[op.id] = 'Concluída'
        else:
            faltas = verificar_consumo(op.produto_id, saldo)
            situacao_material[op.id] = 'Material crítico' if faltas else 'Material OK'
    return render_template(
        'ordens.html',
        ordens=ordens,
        status=status,
        busca=busca,
        prioridade=prioridade,
        produto_id=produto_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        produtos_filtro=Produto.query.order_by(Produto.codigo).all(),
        situacao_material=situacao_material,
        current_user=current_user
    )


@ordens_bp.route('/nova', methods=['GET', 'POST'])
@login_required
@permissao_requerida('criar_op')
def nova():
    produtos = Produto.query.filter(
        Produto.tipo.in_(['SA', 'PA']),
        Produto.status == 'Ativo'
    ).order_by(Produto.codigo).all()
    
    if request.method == 'POST':
        try:
            numero = request.form['numero'].strip()
            if OrdemProducao.query.filter_by(numero=numero).first():
                flash('Número da OP já existe.', 'danger')
                return render_template('ordens.html', produtos=produtos)
            
            op = OrdemProducao(
                numero=numero,
                produto_id=int(request.form['produto_id']),
                quantidade_planejada=float(request.form['quantidade_planejada']),
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                prioridade=request.form.get('prioridade', 'Normal'),
                observacao=request.form.get('observacao', '')
            )
            db.session.add(op)
            db.session.flush()
            db.session.add(Historico(
                op_id=op.id,
                descricao=f'OP {op.numero} criada por {current_user.nome}.'
            ))
            db.session.commit()
            flash('OP criada com sucesso!', 'success')
            return redirect(url_for('ordens.detalhe', id=op.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
    
    return render_template(
        'ordens.html',
        produtos=produtos,
        current_user=current_user
    )


@ordens_bp.route('/<int:id>')
@login_required
@permissao_requerida('ver_ordens')
def detalhe(id):
    op = OrdemProducao.query.get_or_404(id)
    historico = Historico.query.filter_by(op_id=op.id).order_by(Historico.data_hora.desc()).all()
    necessidades = calcular_necessidades_recursivo(op.produto_id, op.quantidade_planejada)
    
    pode_editar = current_user.perfil in ['Analista', 'Supervisor']
    pode_apontar = current_user.tem_permissao('apontar_producao')
    
    return render_template(
        'ordens.html',
        op=op,
        necessidades=necessidades,
        historico=historico,
        pode_editar=pode_editar,
        pode_apontar=pode_apontar,
        current_user=current_user
    )


@ordens_bp.route('/<int:id>/apontar')
@login_required
@permissao_requerida('apontar_producao')
def apontar(id):
    """Abre o formulário de apontamento dentro da própria OP."""
    op = OrdemProducao.query.get_or_404(id)
    operadores = Operador.query.filter_by(status='Ativo').order_by(Operador.nome).all()
    return render_template('ordens.html', op=op, apontar=True, operadores=operadores, current_user=current_user)


@ordens_bp.route('/<int:id>/status/<novo>', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def status(id, novo):
    op = OrdemProducao.query.get_or_404(id)
    validos = set(TRANSICOES_STATUS)
    
    if novo not in validos:
        flash('Status inválido.', 'danger')
        return redirect(url_for('ordens.detalhe', id=id))
    
    if novo not in TRANSICOES_STATUS.get(op.status, set()):
        flash(f'Transição inválida: {op.status} → {novo}.', 'danger')
        return redirect(url_for('ordens.detalhe', id=id))
    
    op.status = novo
    db.session.add(Historico(
        op_id=op.id,
        descricao=f'OP {op.numero}: status alterado para {novo} por {current_user.nome}.'
    ))
    db.session.commit()
    flash('Status atualizado com sucesso!', 'success')
    return redirect(url_for('ordens.detalhe', id=id))


@ordens_bp.route('/<int:id>/reabrir', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def reabrir(id):
    """Reabre uma OP cancelada para novo planejamento."""
    op = OrdemProducao.query.get_or_404(id)
    if op.status != 'Cancelada':
        flash('Somente OPs canceladas podem ser reabertas.', 'warning')
        return redirect(url_for('ordens.detalhe', id=id))

    op.status = 'Planejada'
    db.session.add(Historico(
        op_id=op.id,
        descricao=f'OP {op.numero} reaberta como Planejada por {current_user.nome}.'
    ))
    db.session.commit()
    flash('OP reaberta com sucesso. Revise o planejamento antes de liberá-la.', 'success')
    return redirect(url_for('ordens.detalhe', id=id))


@ordens_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def delete(id):
    op = OrdemProducao.query.get_or_404(id)
    
    if op.status != 'Planejada':
        flash('Apenas OP em status Planejada podem ser excluídas.', 'danger')
        return redirect(url_for('ordens.detalhe', id=id))
    
    try:
        db.session.delete(op)
        db.session.commit()
        flash(f'OP {op.numero} excluída com sucesso!', 'success')
        return redirect(url_for('ordens.index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir OP: {str(e)}', 'danger')
        return redirect(url_for('ordens.detalhe', id=id))
