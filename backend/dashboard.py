# backend/dashboard.py
from flask import Blueprint, render_template, url_for
from flask_login import login_required, current_user
from datetime import date, timedelta
from sqlalchemy import func
from backend.models import OrdemProducao, Produto, Movimentacao, Apontamento
from backend.auth import permissao_requerida

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
@permissao_requerida('ver_dashboard')
def index():
    hoje = date.today()
    
    ops_producao = OrdemProducao.query.filter_by(status='Em produção').count()
    ops_pendentes = OrdemProducao.query.filter(
        OrdemProducao.status.in_(['Planejada', 'Liberada', 'Pausada'])
    ).count()
    ops_concluidas = OrdemProducao.query.filter_by(status='Concluída').count()
    
    producao_dia = (
        Movimentacao.query.filter(
            Movimentacao.tipo == 'Produção',
            func.date(Movimentacao.data_hora) == hoje
        ).with_entities(func.coalesce(func.sum(Movimentacao.quantidade), 0)).scalar() or 0
    )
    refugo_dia = (
        Apontamento.query.filter(func.date(Apontamento.data_hora) == hoje)
        .with_entities(func.coalesce(func.sum(Apontamento.quantidade_refugada), 0)).scalar() or 0
    )
    status_finalizados = ['Concluída', 'Cancelada']
    ops_atrasadas = OrdemProducao.query.filter(
        OrdemProducao.data < hoje,
        OrdemProducao.status.notin_(status_finalizados)
    ).order_by(OrdemProducao.data.asc()).all()
    produtos_criticos = Produto.query.filter(
        Produto.status == 'Ativo', Produto.estoque_atual < Produto.estoque_minimo
    ).order_by((Produto.estoque_minimo - Produto.estoque_atual).desc()).all()
    produtos_zerados = Produto.query.filter(Produto.status == 'Ativo', Produto.estoque_atual <= 0).count()

    inicio_periodo = hoje - timedelta(days=6)
    producao_por_dia = {
        dia: float(
            db_total or 0
        ) for dia, db_total in (
            Movimentacao.query.with_entities(func.date(Movimentacao.data_hora), func.sum(Movimentacao.quantidade))
            .filter(Movimentacao.tipo == 'Produção', func.date(Movimentacao.data_hora) >= inicio_periodo)
            .group_by(func.date(Movimentacao.data_hora)).all()
        )
    }
    planejado_por_dia = {
        dia: float(total or 0) for dia, total in (
            OrdemProducao.query.with_entities(OrdemProducao.data, func.sum(OrdemProducao.quantidade_planejada))
            .filter(OrdemProducao.data >= inicio_periodo).group_by(OrdemProducao.data).all()
        )
    }
    dias = [inicio_periodo + timedelta(days=indice) for indice in range(7)]
    grafico_producao = {
        'labels': [dia.strftime('%d/%m') for dia in dias],
        'planejado': [planejado_por_dia.get(dia, planejado_por_dia.get(dia.isoformat(), 0)) for dia in dias],
        'realizado': [producao_por_dia.get(dia.isoformat(), 0) for dia in dias],
    }
    status_ordens = ['Planejada', 'Liberada', 'Em produção', 'Pausada', 'Concluída', 'Cancelada']
    contagem_status = dict(
        OrdemProducao.query.with_entities(OrdemProducao.status, func.count(OrdemProducao.id)).group_by(OrdemProducao.status).all()
    )
    grafico_status = {'labels': status_ordens, 'valores': [contagem_status.get(status, 0) for status in status_ordens]}

    estruturas_incompletas = [
        produto for produto in Produto.query.filter(Produto.tipo.in_(['SA', 'PA']), Produto.status == 'Ativo').all()
        if not produto.componentes
    ][:5]
    atencoes = []
    atencoes.extend({'nivel': 'danger', 'titulo': f'{op.numero} atrasada', 'descricao': f'Prevista para {op.data.strftime("%d/%m/%Y")}', 'url': url_for('ordens.detalhe', id=op.id)} for op in ops_atrasadas[:4])
    atencoes.extend({'nivel': 'warning', 'titulo': f'{produto.codigo} abaixo do mínimo', 'descricao': f'{produto.estoque_atual:g} {produto.unidade} disponível de {produto.estoque_minimo:g} {produto.unidade}', 'url': url_for('estoque.index')} for produto in produtos_criticos[:4])
    atencoes.extend({'nivel': 'info', 'titulo': f'{produto.codigo} sem estrutura', 'descricao': 'Defina a BOM antes de planejar a produção.', 'url': url_for('produtos.index')} for produto in estruturas_incompletas[:3])
    
    mostrar_administrativo = current_user.perfil in ['Analista', 'Supervisor']
    mostrar_apontamentos = current_user.tem_permissao('ver_apontamentos')
    
    return render_template(
        'dashboard.html',
        ops_producao=ops_producao,
        ops_pendentes=ops_pendentes,
        ops_concluidas=ops_concluidas,
        producao_dia=producao_dia,
        refugo_dia=refugo_dia,
        ops_atrasadas=ops_atrasadas,
        produtos_criticos=produtos_criticos,
        produtos_zerados=produtos_zerados,
        grafico_producao=grafico_producao,
        grafico_status=grafico_status,
        atencoes=atencoes,
        ordens_recentes=OrdemProducao.query.order_by(OrdemProducao.criada_em.desc()).limit(6).all(),
        movimentacoes_recentes=Movimentacao.query.order_by(Movimentacao.data_hora.desc()).limit(6).all(),
        produtos=Produto.query.order_by(Produto.codigo).all(),
        mostrar_administrativo=mostrar_administrativo,
        mostrar_apontamentos=mostrar_apontamentos,
        current_user=current_user
    )
