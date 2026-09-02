# backend/utils.py
from backend.models import Produto, Estrutura


def get_tipo_nome(tipo):
    """Retorna o nome descritivo do tipo de produto"""
    tipos = {'MP': 'Matéria-prima', 'SA': 'Semiacabado', 'PA': 'Acabado'}
    return tipos.get(tipo, tipo)


def get_tipos_permitidos(tipo_produto):
    """Retorna os tipos permitidos como componentes para um produto"""
    if tipo_produto == 'MP':
        return []
    elif tipo_produto == 'SA':
        return ['MP']
    elif tipo_produto == 'PA':
        return ['MP', 'SA']
    return []


def validar_circular(produto_pai_id, componente_id, visited=None):
    """Valida se a estrutura não tem circularidade"""
    if visited is None:
        visited = set()
    
    if componente_id in visited:
        return False
    
    visited.add(componente_id)
    
    componentes = Estrutura.query.filter_by(produto_pai_id=componente_id).all()
    for comp in componentes:
        if comp.componente_id == produto_pai_id:
            return False
        if not validar_circular(produto_pai_id, comp.componente_id, visited.copy()):
            return False
    
    return True


def get_estoque_disponivel(produto_id):
    """Retorna o estoque atual de um produto"""
    produto = Produto.query.get(produto_id)
    if produto:
        return produto.estoque_atual
    return 0.0