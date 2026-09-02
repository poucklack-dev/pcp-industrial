# backend/relatorios.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from backend.models import db, Movimentacao, OrdemProducao, Apontamento, Produto, Historico
from backend.auth import permissao_requerida
from sqlalchemy import func, extract
from datetime import datetime, timedelta

relatorios_bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')


@relatorios_bp.route('/')
@login_required
@permissao_requerida('ver_relatorios')
def index():
    producao = Movimentacao.query.filter_by(tipo='Produção').order_by(Movimentacao.data_hora.desc()).all()
    consumos = Movimentacao.query.filter_by(tipo='Consumo de produção').order_by(Movimentacao.data_hora.desc()).all()
    ops = OrdemProducao.query.order_by(OrdemProducao.id.desc()).all()
    
    pode_editar = current_user.perfil in ['Analista', 'Supervisor']
    
    return render_template(
        'relatorios.html',
        producao=producao,
        consumos=consumos,
        ops=ops,
        pode_editar=pode_editar
    )


@relatorios_bp.route('/producao/mensal')
@login_required
@permissao_requerida('ver_relatorios')
def producao_mensal():
    try:
        mes = int(request.args.get('mes', datetime.now().month))
        ano = int(request.args.get('ano', datetime.now().year))
        
        resultados = db.session.query(
            func.sum(Movimentacao.quantidade).label('total'),
            func.count(Movimentacao.id).label('registros')
        ).filter(
            Movimentacao.tipo == 'Produção',
            extract('month', Movimentacao.data_hora) == mes,
            extract('year', Movimentacao.data_hora) == ano
        ).first()
        
        return jsonify({
            'success': True,
            'total': float(resultados.total) if resultados.total else 0,
            'registros': resultados.registros or 0,
            'mes': mes,
            'ano': ano
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@relatorios_bp.route('/consumo/detalhado')
@login_required
@permissao_requerida('ver_relatorios')
def consumo_detalhado():
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        query = Movimentacao.query.filter_by(tipo='Consumo de produção')
        
        if data_inicio:
            query = query.filter(Movimentacao.data_hora >= datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim:
            query = query.filter(Movimentacao.data_hora <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
        
        resultados = query.order_by(Movimentacao.data_hora.desc()).all()
        
        dados = [{
            'id': r.id,
            'produto_codigo': r.produto.codigo,
            'produto_descricao': r.produto.descricao,
            'quantidade': abs(r.quantidade),
            'op_numero': r.op.numero if r.op else '-',
            'data_hora': r.data_hora.strftime('%d/%m/%Y %H:%M'),
            'usuario': r.usuario
        } for r in resultados]
        
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@relatorios_bp.route('/ops/status')
@login_required
@permissao_requerida('ver_relatorios')
def ops_status():
    try:
        status_contagem = db.session.query(
            OrdemProducao.status,
            func.count(OrdemProducao.id).label('total'),
            func.sum(OrdemProducao.quantidade_planejada).label('total_planejado'),
            func.sum(OrdemProducao.quantidade_produzida).label('total_produzido')
        ).group_by(OrdemProducao.status).all()
        
        dados = [{
            'status': s.status,
            'total': s.total,
            'total_planejado': float(s.total_planejado) if s.total_planejado else 0,
            'total_produzido': float(s.total_produzido) if s.total_produzido else 0,
            'percentual': (float(s.total_produzido) / float(s.total_planejado) * 100) if s.total_planejado else 0
        } for s in status_contagem]
        
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@relatorios_bp.route('/apontamentos/periodo')
@login_required
@permissao_requerida('ver_relatorios')
def apontamentos_periodo():
    try:
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        query = Apontamento.query
        
        if data_inicio:
            query = query.filter(Apontamento.data_hora >= datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim:
            query = query.filter(Apontamento.data_hora <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
        
        apontamentos = query.order_by(Apontamento.data_hora.desc()).all()
        
        dados = [{
            'id': a.id,
            'op_numero': a.op.numero,
            'produto_codigo': a.op.produto.codigo,
            'produto_descricao': a.op.produto.descricao,
            'quantidade_produzida': a.quantidade_produzida,
            'quantidade_boa': a.quantidade_boa,
            'quantidade_refugada': a.quantidade_refugada,
            'motivo_refugo': a.motivo_refugo,
            'operador': a.operador.nome if a.operador else '-',
            'data_hora': a.data_hora.strftime('%d/%m/%Y %H:%M')
        } for a in apontamentos]
        
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@relatorios_bp.route('/estoque/critico')
@login_required
@permissao_requerida('ver_relatorios')
def estoque_critico():
    try:
        produtos_criticos = Produto.query.filter(
            Produto.estoque_atual <= Produto.estoque_minimo,
            Produto.status == 'Ativo'
        ).order_by(
            (Produto.estoque_minimo - Produto.estoque_atual).desc()
        ).all()
        
        dados = [{
            'id': p.id,
            'codigo': p.codigo,
            'descricao': p.descricao,
            'tipo': p.tipo,
            'tipo_nome': {'MP': 'Matéria-prima', 'SA': 'Semi-acabado', 'PA': 'Acabado'}.get(p.tipo, p.tipo),
            'unidade': p.unidade,
            'estoque_atual': p.estoque_atual,
            'estoque_minimo': p.estoque_minimo,
            'faltando': p.estoque_minimo - p.estoque_atual
        } for p in produtos_criticos]
        
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@relatorios_bp.route('/historico/op/<int:op_id>')
@login_required
@permissao_requerida('ver_relatorios')
def historico_op(op_id):
    try:
        historicos = Historico.query.filter_by(op_id=op_id).order_by(Historico.data_hora.desc()).all()
        
        dados = [{
            'id': h.id,
            'descricao': h.descricao,
            'data_hora': h.data_hora.strftime('%d/%m/%Y %H:%M')
        } for h in historicos]
        
        return jsonify({'success': True, 'dados': dados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
