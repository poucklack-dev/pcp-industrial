"""Unidades padronizadas e conversões usadas pelo PCP."""

UNIDADES = [
    {'codigo': 'UN', 'nome': 'Unidade', 'dimensao': 'unidade', 'fator': 1},
    {'codigo': 'DZ', 'nome': 'Dúzia', 'dimensao': 'unidade', 'fator': 12},
    {'codigo': 'KG', 'nome': 'Quilograma', 'dimensao': 'massa', 'fator': 1},
    {'codigo': 'G', 'nome': 'Grama', 'dimensao': 'massa', 'fator': 0.001},
    {'codigo': 'MG', 'nome': 'Miligrama', 'dimensao': 'massa', 'fator': 0.000001},
    {'codigo': 'L', 'nome': 'Litro', 'dimensao': 'volume', 'fator': 1},
    {'codigo': 'ML', 'nome': 'Mililitro', 'dimensao': 'volume', 'fator': 0.001},
    {'codigo': 'M', 'nome': 'Metro', 'dimensao': 'comprimento', 'fator': 1},
    {'codigo': 'CM', 'nome': 'Centímetro', 'dimensao': 'comprimento', 'fator': 0.01},
    {'codigo': 'MM', 'nome': 'Milímetro', 'dimensao': 'comprimento', 'fator': 0.001},
]

_POR_CODIGO = {u['codigo']: u for u in UNIDADES}
_ALIASES = {'UND': 'UN', 'UNID': 'UN', 'UNIDADE': 'UN', 'LT': 'L', 'LITRO': 'L', 'GRAMAS': 'G'}


def normalizar_unidade(unidade):
    codigo = str(unidade or '').strip().upper()
    codigo = _ALIASES.get(codigo, codigo)
    if codigo not in _POR_CODIGO:
        raise ValueError('Unidade inválida. Escolha uma unidade padronizada.')
    return codigo


def unidades_compativeis(unidade):
    unidade = normalizar_unidade(unidade)
    dimensao = _POR_CODIGO[unidade]['dimensao']
    return [u for u in UNIDADES if u['dimensao'] == dimensao]


def converter(quantidade, origem, destino):
    origem = normalizar_unidade(origem)
    destino = normalizar_unidade(destino)
    unidade_origem, unidade_destino = _POR_CODIGO[origem], _POR_CODIGO[destino]
    if unidade_origem['dimensao'] != unidade_destino['dimensao']:
        raise ValueError(f'Não é possível converter {origem} para {destino}.')
    return float(quantidade) * unidade_origem['fator'] / unidade_destino['fator']
