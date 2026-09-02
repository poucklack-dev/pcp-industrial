# backend/produtos.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from backend.models import db, Produto, Maquina, Estrutura, Historico
from backend.auth import permissao_requerida
from backend.unidades import UNIDADES, converter, normalizar_unidade, unidades_compativeis

produtos_bp = Blueprint('produtos', __name__, url_prefix='/produtos')


def get_tipo_nome(tipo):
    tipos = {'MP': 'Matéria-prima', 'SA': 'Semiacabado', 'PA': 'Acabado'}
    return tipos.get(tipo, tipo)


def get_tipos_permitidos(tipo_produto):
    if tipo_produto == 'MP':
        return []
    elif tipo_produto == 'SA':
        return ['MP']
    elif tipo_produto == 'PA':
        return ['MP', 'SA']
    return []


def validar_circular(produto_pai_id, componente_id, visited=None):
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


@produtos_bp.route('/')
@login_required
@permissao_requerida('ver_produtos')
def index():
    busca = request.args.get('busca', '')
    # A operação normalmente começa pelo produto acabado; as demais categorias
    # permanecem acessíveis pelas abas da própria tela.
    tipo = request.args.get('tipo', 'PA').upper()
    if tipo not in {'MP', 'SA', 'PA'}:
        tipo = 'PA'
    q = Produto.query
    
    if busca:
        q = q.filter(
            (Produto.codigo.ilike(f'%{busca}%')) |
            (Produto.descricao.ilike(f'%{busca}%'))
        )
    q = q.filter_by(tipo=tipo)
    
    maquinas = Maquina.query.filter_by(status='Ativo').order_by(Maquina.codigo).all()
    maquinas_json = [{'id': m.id, 'codigo': m.codigo, 'nome': m.nome} for m in maquinas]
    
    pode_editar = current_user.perfil in ['Analista', 'Supervisor']
    
    return render_template(
        'produtos.html',
        produtos=q.order_by(Produto.codigo).all(),
        busca=busca,
        tipo=tipo,
        maquinas=maquinas_json,
        unidades=UNIDADES,
        pode_editar=pode_editar,
        current_user=current_user
    )


@produtos_bp.route('/<int:id>/detalhe_json')
@login_required
@permissao_requerida('ver_produtos')
def detalhe_json(id):
    try:
        produto = Produto.query.get_or_404(id)
        
        estrutura = []
        if produto.tipo in ['SA', 'PA']:
            for item in produto.componentes:
                unidade_uso = item.unidade_consumo or item.componente.unidade
                quantidade_uso = converter(item.quantidade, item.componente.unidade, unidade_uso)
                estrutura.append({
                    'id': item.id,
                    'componente_id': item.componente_id,
                    'componente_codigo': item.componente.codigo,
                    'componente_descricao': item.componente.descricao,
                    'componente_tipo': item.componente.tipo,
                    'componente_tipo_nome': get_tipo_nome(item.componente.tipo),
                    'componente_unidade': item.componente.unidade,
                    'componente_estoque': item.componente.estoque_atual,
                    'componente_estoque_minimo': item.componente.estoque_minimo,
                    'quantidade': quantidade_uso,
                    'unidade_uso': unidade_uso,
                    'observacao': item.observacao
                })
        
        return jsonify({
            'id': produto.id,
            'codigo': produto.codigo,
            'descricao': produto.descricao,
            'tipo': produto.tipo,
            'tipo_nome': get_tipo_nome(produto.tipo),
            'unidade': produto.unidade,
            'estoque_atual': produto.estoque_atual,
            'estoque_minimo': produto.estoque_minimo,
            'status': produto.status,
            'observacao': produto.observacao,
            'maquina': {
                'id': produto.maquina.id if produto.maquina else None,
                'codigo': produto.maquina.codigo if produto.maquina else None,
                'nome': produto.maquina.nome if produto.maquina else None
            } if produto.maquina else None,
            'estrutura': estrutura,
            'tem_estrutura': len(estrutura) > 0,
            'pode_ter_estrutura': produto.tipo in ['SA', 'PA'],
            'tipos_permitidos': get_tipos_permitidos(produto.tipo)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@produtos_bp.route('/<int:id>/estrutura')
@login_required
@permissao_requerida('ver_estrutura')
def obter_estrutura(id):
    """Fornece ao modal a estrutura, inclusive quando ainda está vazia."""
    produto = Produto.query.get_or_404(id)

    if produto.tipo not in ['SA', 'PA']:
        return jsonify({
            'success': False,
            'message': 'Somente produtos semiacabados ou acabados possuem estrutura.'
        }), 400

    componentes = []
    for item in produto.componentes:
        unidade_uso = item.unidade_consumo or item.componente.unidade
        quantidade_uso = converter(item.quantidade, item.componente.unidade, unidade_uso)
        componentes.append({
            'id': item.id,
            'componente_codigo': item.componente.codigo,
            'componente_descricao': item.componente.descricao,
            'componente_tipo_nome': get_tipo_nome(item.componente.tipo),
            'componente_unidade': item.componente.unidade,
            'componente_estoque': item.componente.estoque_atual,
            'componente_estoque_minimo': item.componente.estoque_minimo,
            'quantidade': quantidade_uso,
            'unidade_uso': unidade_uso,
        })

    return jsonify({
        'success': True,
        'produto_id': produto.id,
        'produto_codigo': produto.codigo,
        'produto_descricao': produto.descricao,
        'total_componentes': len(componentes),
        'componentes': componentes,
    })


@produtos_bp.route('/novo', methods=['POST'])
@login_required
@permissao_requerida('criar_op')
def novo():
    try:
        p = Produto(
            codigo=request.form['codigo'].strip(),
            descricao=request.form['descricao'].strip(),
            tipo=request.form['tipo'],
            unidade=normalizar_unidade(request.form['unidade']),
            estoque_atual=float(request.form.get('estoque_atual') or 0),
            estoque_minimo=float(request.form.get('estoque_minimo') or 0),
            status=request.form.get('status', 'Ativo'),
            observacao=request.form.get('observacao'),
            maquina_id=int(request.form['maquina_id']) if request.form.get('maquina_id') else None
        )
        
        if p.tipo != 'MP':
            p.maquina_id = None
        
        db.session.add(p)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Produto cadastrado com sucesso!',
            'produto': {
                'id': p.id,
                'codigo': p.codigo,
                'descricao': p.descricao,
                'tipo': p.tipo,
                'unidade': p.unidade,
                'estoque_atual': p.estoque_atual,
                'estoque_minimo': p.estoque_minimo,
                'status': p.status
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@produtos_bp.route('/<int:id>/editar', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def editar(id):
    try:
        p = Produto.query.get_or_404(id)
        p.codigo = request.form['codigo'].strip()
        p.descricao = request.form['descricao'].strip()
        p.tipo = request.form['tipo']
        nova_unidade = normalizar_unidade(request.form['unidade'])
        if nova_unidade != p.unidade and (p.componentes or p.produtos_pai):
            raise ValueError('Não altere a unidade de um produto que já possui estrutura. Crie uma nova referência ou ajuste a BOM.')
        p.unidade = nova_unidade
        p.estoque_minimo = float(request.form.get('estoque_minimo') or 0)
        p.status = request.form.get('status', 'Ativo')
        p.observacao = request.form.get('observacao')
        p.maquina_id = int(request.form['maquina_id']) if p.tipo == 'MP' and request.form.get('maquina_id') else None
        
        if p.tipo in ['SA', 'PA']:
            p.maquina_id = None
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Produto atualizado com sucesso!',
            'produto': {
                'id': p.id,
                'codigo': p.codigo,
                'descricao': p.descricao,
                'tipo': p.tipo,
                'unidade': p.unidade,
                'estoque_atual': p.estoque_atual,
                'estoque_minimo': p.estoque_minimo,
                'status': p.status
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@produtos_bp.route('/<int:id>/excluir', methods=['DELETE'])
@login_required
@permissao_requerida('editar_op')
def excluir(id):
    try:
        produto = Produto.query.get_or_404(id)
        
        if produto.componentes:
            return jsonify({
                'success': False,
                'message': f'Produto possui estrutura com {len(produto.componentes)} componentes.'
            }), 400
        
        if produto.produtos_pai:
            return jsonify({
                'success': False,
                'message': f'Produto é componente de {len(produto.produtos_pai)} produto(s).'
            }), 400
        
        db.session.delete(produto)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Produto {produto.codigo} excluído com sucesso!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@produtos_bp.route('/<int:id>/estrutura/adicionar', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def adicionar_componente(id):
    try:
        produto = Produto.query.get_or_404(id)
        
        if produto.tipo not in ['SA', 'PA']:
            return jsonify({
                'success': False,
                'message': 'Apenas Semi-acabados ou Acabados podem ter estrutura.'
            }), 400
        
        componente_id = int(request.form.get('componente_id'))
        quantidade = float(request.form.get('quantidade', 0))
        observacao = request.form.get('observacao', '')
        
        if quantidade <= 0:
            return jsonify({'success': False, 'message': 'Quantidade deve ser maior que zero.'}), 400
        
        if componente_id == id:
            return jsonify({'success': False, 'message': 'Produto não pode ser componente de si mesmo.'}), 400
        
        componente = Produto.query.get(componente_id)
        if not componente:
            return jsonify({'success': False, 'message': 'Componente não encontrado.'}), 404
        
        tipos_permitidos = get_tipos_permitidos(produto.tipo)
        if componente.tipo not in tipos_permitidos:
            return jsonify({
                'success': False,
                'message': f'{get_tipo_nome(componente.tipo)} não pode ser componente de {get_tipo_nome(produto.tipo)}.'
            }), 400
        
        if componente.status != 'Ativo':
            return jsonify({
                'success': False,
                'message': f'Componente {componente.codigo} está inativo.'
            }), 400

        unidade_consumo = normalizar_unidade(request.form.get('unidade_consumo') or componente.unidade)
        if unidade_consumo not in [u['codigo'] for u in unidades_compativeis(componente.unidade)]:
            return jsonify({'success': False, 'message': 'A unidade de consumo não é compatível com o componente.'}), 400
        quantidade_base = converter(quantidade, unidade_consumo, componente.unidade)
        
        existing = Estrutura.query.filter_by(
            produto_pai_id=id,
            componente_id=componente_id
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'message': 'Componente já está na estrutura.'
            }), 400
        
        if not validar_circular(id, componente_id):
            return jsonify({
                'success': False,
                'message': 'Estrutura circular detectada.'
            }), 400
        
        estrutura = Estrutura(
            produto_pai_id=id,
            componente_id=componente_id,
            quantidade=quantidade_base,
            unidade_consumo=unidade_consumo,
            perda_percentual=0,
            observacao=observacao
        )
        
        db.session.add(estrutura)
        db.session.add(Historico(
            descricao=f'Componente {componente.codigo} adicionado à estrutura de {produto.codigo} por {current_user.nome}'
        ))
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Componente {componente.codigo} adicionado com sucesso!',
            'estrutura': {
                'id': estrutura.id,
                'componente_id': componente_id,
                'componente_codigo': componente.codigo,
                'componente_descricao': componente.descricao,
                'componente_tipo': componente.tipo,
                'componente_tipo_nome': get_tipo_nome(componente.tipo),
                'componente_unidade': componente.unidade,
                'componente_estoque': componente.estoque_atual,
                'componente_estoque_minimo': componente.estoque_minimo,
                'quantidade': quantidade,
                'unidade_uso': unidade_consumo,
                'observacao': observacao
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@produtos_bp.route('/estrutura/<int:estrutura_id>/remover', methods=['DELETE'])
@login_required
@permissao_requerida('editar_op')
def remover_componente(estrutura_id):
    try:
        estrutura = Estrutura.query.get_or_404(estrutura_id)
        
        codigo_componente = estrutura.componente.codigo
        codigo_pai = estrutura.produto_pai.codigo
        
        db.session.delete(estrutura)
        db.session.add(Historico(
            descricao=f'Componente {codigo_componente} removido da estrutura de {codigo_pai} por {current_user.nome}'
        ))
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Componente removido com sucesso!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@produtos_bp.route('/estrutura/<int:estrutura_id>/editar', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def editar_componente(estrutura_id):
    try:
        estrutura = Estrutura.query.get_or_404(estrutura_id)
        
        quantidade = float(request.form.get('quantidade', 0))
        observacao = request.form.get('observacao', '')
        
        if quantidade <= 0:
            return jsonify({'success': False, 'message': 'Quantidade deve ser maior que zero.'}), 400
        
        unidade_consumo = estrutura.unidade_consumo or estrutura.componente.unidade
        estrutura.quantidade = converter(quantidade, unidade_consumo, estrutura.componente.unidade)
        # O consumo da BOM é direto; perdas são registradas durante a execução.
        estrutura.perda_percentual = 0
        estrutura.observacao = observacao
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Componente atualizado com sucesso!',
            'estrutura': {
                'id': estrutura.id,
                'componente_id': estrutura.componente_id,
                'componente_codigo': estrutura.componente.codigo,
                'componente_descricao': estrutura.componente.descricao,
                'componente_tipo': estrutura.componente.tipo,
                'componente_tipo_nome': get_tipo_nome(estrutura.componente.tipo),
                'componente_unidade': estrutura.componente.unidade,
                'componente_estoque': estrutura.componente.estoque_atual,
                'componente_estoque_minimo': estrutura.componente.estoque_minimo,
                'quantidade': quantidade,
                'unidade_uso': unidade_consumo,
                'observacao': observacao
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@produtos_bp.route('/componentes_disponiveis')
@login_required
@permissao_requerida('ver_estrutura')
def componentes_disponiveis():
    try:
        componentes = Produto.query.filter(
            Produto.tipo.in_(['MP', 'SA']),
            Produto.status == 'Ativo'
        ).order_by(Produto.codigo).all()
        
        return jsonify([{
            'id': c.id,
            'codigo': c.codigo,
            'descricao': c.descricao,
            'tipo': c.tipo,
            'tipo_nome': get_tipo_nome(c.tipo),
            'unidade': c.unidade,
            'unidades_uso': unidades_compativeis(c.unidade),
            'estoque_atual': c.estoque_atual,
            'estoque_minimo': c.estoque_minimo
        } for c in componentes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
