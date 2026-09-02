# backend/services.py
from backend.models import db, Estrutura, Movimentacao, Historico, Configuracao, Produto
from flask_login import current_user


def explosao_direta(produto_id, quantidade):
    """Retorna a lista de componentes diretos com quantidade necessária"""
    return [
        (e.componente, e.quantidade * quantidade)
        for e in Estrutura.query.filter_by(produto_pai_id=produto_id).all()
    ]


def verificar_consumo(produto_id, quantidade):
    """Verifica se há estoque suficiente para consumir os componentes"""
    config = Configuracao.query.first()
    faltas = []

    def rec(pid, qty, caminho=None):
        caminho = caminho or set()
        if pid in caminho:
            return
        for e in Estrutura.query.filter_by(produto_pai_id=pid).all():
            necessidade = e.quantidade * qty
            comp = e.componente
            if comp.tipo in ('SA', 'PA') and Estrutura.query.filter_by(produto_pai_id=comp.id).first():
                continue
            if comp.estoque_atual < necessidade and not config.permitir_estoque_negativo:
                faltas.append((comp, necessidade, comp.estoque_atual, necessidade - comp.estoque_atual))
    
    rec(produto_id, quantidade)
    return faltas


def consumir_componentes(op, quantidade, apontamento_id):
    """Consome componentes da estrutura do produto"""
    componentes = explosao_direta(op.produto_id, quantidade)
    config = Configuracao.query.first()
    
    usuario = current_user.nome if current_user.is_authenticated else 'Sistema'

    for comp, necessidade in componentes:
        if comp.estoque_atual < necessidade and not config.permitir_estoque_negativo:
            raise ValueError(
                f'Estoque insuficiente: {comp.codigo} - necessário {necessidade:g}, '
                f'disponível {comp.estoque_atual:g}'
            )

        comp.estoque_atual -= necessidade
        db.session.add(Movimentacao(
            produto_id=comp.id,
            quantidade=-necessidade,
            tipo='Consumo de produção',
            op_id=op.id,
            apontamento_id=apontamento_id,
            usuario=usuario,
            observacao=f'Consumo automático da OP {op.numero}'
        ))
        db.session.add(Historico(
            op_id=op.id,
            descricao=f'Consumo automático: {necessidade:g} {comp.unidade} de {comp.codigo}.'
        ))


def registrar_producao(op, quantidade, apontamento_id):
    """Registra a produção do produto acabado/semi-acabado"""
    produto = op.produto
    produto.estoque_atual += quantidade
    
    usuario = current_user.nome if current_user.is_authenticated else 'Sistema'
    
    db.session.add(Movimentacao(
        produto_id=produto.id,
        quantidade=quantidade,
        tipo='Produção',
        op_id=op.id,
        apontamento_id=apontamento_id,
        usuario=usuario,
        observacao=f'Produção boa da OP {op.numero}'
    ))


def calcular_necessidades_recursivo(produto_id, quantidade_planejada):
    """Explode a BOM multinível, inclui intermediários e aplica perdas."""
    resultado = {}

    def visitar(pid, quantidade, caminho):
        if pid in caminho:
            raise ValueError('Estrutura circular detectada durante a explosão da BOM.')
        novo_caminho = caminho | {pid}
        for item in Estrutura.query.filter_by(produto_pai_id=pid).all():
            necessidade = quantidade * item.quantidade * (1 + float(item.perda_percentual or 0) / 100)
            registro = resultado.setdefault(item.componente_id, {
                'produto': item.componente,
                'quantidade': 0.0,
                'unidade': item.componente.unidade,
            })
            registro['quantidade'] += necessidade
            if Estrutura.query.filter_by(produto_pai_id=item.componente_id).first():
                visitar(item.componente_id, necessidade, novo_caminho)

    visitar(produto_id, float(quantidade_planejada), set())
    return resultado
