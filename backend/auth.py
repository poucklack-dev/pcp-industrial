# backend/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime
from urllib.parse import urlparse, urljoin
from backend.models import db, Usuario, Operador

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

PERFIS = ('Supervisor', 'Analista', 'Líder de Produção', 'Operador')
HIERARQUIA = {'Operador': 1, 'Líder de Produção': 2, 'Analista': 3, 'Supervisor': 4}


def normalizar_perfil(perfil):
    return {'Apontador': 'Operador', 'Lider de Producao': 'Líder de Produção'}.get(perfil, perfil)


def rota_inicial_usuario(usuario):
    return 'apontamentos.index' if normalizar_perfil(usuario.perfil) == 'Operador' else 'dashboard.index'


def proxima_url_segura(destino):
    """Aceita apenas retornos internos após o login."""
    if not destino:
        return False
    destino_absoluto = urlparse(urljoin(request.host_url, destino))
    origem = urlparse(request.host_url)
    return destino_absoluto.scheme in ('http', 'https') and destino_absoluto.netloc == origem.netloc

def permissao_requerida(permissao):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Você precisa estar logado para acessar esta página.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if not current_user.tem_permissao(permissao):
                abort(403, description='Você não tem permissão para acessar esta página.')
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def perfil_requerido(perfil):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Você precisa estar logado para acessar esta página.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.perfil != perfil:
                flash(f'Apenas usuários com perfil {perfil} podem acessar esta página.', 'danger')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email, ativo=True).first()
        
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            usuario.ultimo_acesso = datetime.now()
            db.session.commit()
            
            flash(f'Bem-vindo, {usuario.nome}!', 'success')
            
            next_page = request.args.get('next')
            if proxima_url_segura(next_page):
                return redirect(next_page)
            return redirect(url_for(rota_inicial_usuario(usuario)))
        else:
            flash('Email ou senha inválidos.', 'danger')
    
    return render_template('login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    flash('A senha é redefinida internamente por um superior, em Usuários.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/criar_usuario', methods=['GET', 'POST'])
def criar_usuario():
    # Verifica se é o primeiro usuário do sistema ou se é supervisor
    primeiro_usuario = Usuario.query.count() == 0
    
    if not primeiro_usuario:
        if not current_user.is_authenticated or not current_user.tem_permissao('gerenciar_usuarios'):
            flash('Apenas Supervisores podem criar novos usuários.', 'danger')
            return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            
            if Usuario.query.filter_by(email=email).first():
                flash('Este email já está cadastrado.', 'danger')
                return redirect(url_for('dashboard.index'))
            
            usuario = Usuario(
                nome=request.form.get('nome'),
                email=email,
                perfil=normalizar_perfil(request.form.get('perfil', 'Operador')),
                ativo=True
            )
            usuario.set_senha(request.form.get('senha'))
            if not primeiro_usuario and not perfil_permitido_para_criacao(usuario.perfil):
                flash('Você não pode criar este perfil.', 'danger')
                return redirect(url_for(rota_inicial_usuario(current_user)))
            
            db.session.add(usuario)
            db.session.flush()
            criar_perfil_operador(usuario)
            db.session.commit()
            
            flash('Usuário criado com sucesso!', 'success')
            
            if primeiro_usuario:
                return redirect(url_for('auth.login'))
            else:
                return redirect(url_for('auth.listar_usuarios'))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar usuário: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard.index') if current_user.is_authenticated else url_for('auth.login'))


def pode_gerenciar_usuario(usuario):
    """Permite gerenciar perfis inferiores; Supervisor também gerencia pares."""
    if usuario.id == current_user.id:
        return False
    perfil_atual = normalizar_perfil(current_user.perfil)
    perfil_alvo = normalizar_perfil(usuario.perfil)
    if perfil_atual == 'Supervisor':
        return perfil_alvo in PERFIS
    return HIERARQUIA.get(perfil_atual, 0) > HIERARQUIA.get(perfil_alvo, 0)


def perfil_permitido_para_criacao(perfil):
    perfil = normalizar_perfil(perfil)
    perfil_atual = normalizar_perfil(current_user.perfil)
    if perfil_atual == 'Supervisor':
        return perfil in PERFIS
    return HIERARQUIA.get(perfil_atual, 0) > HIERARQUIA.get(perfil, 0)


def criar_perfil_operador(usuario):
    """Toda conta Operador também existe como recurso apontável na produção."""
    if usuario.perfil != 'Operador' or Operador.query.filter_by(usuario_id=usuario.id).first():
        return
    db.session.add(Operador(codigo=f'OP-{usuario.id:04d}', nome=usuario.nome, setor='Produção', status='Ativo', usuario_id=usuario.id))


def resposta_usuarios(mensagem, sucesso=True, status=200):
    if request.args.get('formato') == 'json':
        return jsonify({'success': sucesso, 'message': mensagem}), status
    flash(mensagem, 'success' if sucesso else 'danger')
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/usuarios')
@login_required
@permissao_requerida('ver_usuarios')
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    if request.args.get('formato') == 'json':
        return jsonify({'success': True, 'data': [
            {'id': u.id, 'nome': u.nome, 'email': u.email, 'perfil': u.perfil, 'ativo': u.ativo}
            for u in usuarios
        ]})
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
@permissao_requerida('gerenciar_usuarios')
def novo_usuario():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            perfil = normalizar_perfil(request.form.get('perfil', 'Operador'))
            if not perfil_permitido_para_criacao(perfil):
                return resposta_usuarios('Você não pode criar este perfil.', False, 403)
            
            if Usuario.query.filter_by(email=email).first():
                return resposta_usuarios('Este email já está cadastrado.', False, 409)
            
            usuario = Usuario(
                nome=request.form.get('nome'),
                email=email,
                perfil=perfil
            )
            usuario.set_senha(request.form.get('senha'))
            
            db.session.add(usuario)
            db.session.flush()
            criar_perfil_operador(usuario)
            db.session.commit()
            
            return resposta_usuarios('Usuário criado com sucesso!')
        except Exception as e:
            db.session.rollback()
            return resposta_usuarios(f'Erro ao criar usuário: {str(e)}', False, 400)
    
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permissao_requerida('gerenciar_usuarios')
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    
    if not pode_gerenciar_usuario(usuario):
        return resposta_usuarios('Você não pode editar este usuário.', False, 403)
    
    if request.method == 'POST':
        try:
            perfil = normalizar_perfil(request.form.get('perfil', usuario.perfil))
            if not perfil_permitido_para_criacao(perfil):
                return resposta_usuarios('Você não pode atribuir este perfil.', False, 403)
            usuario.nome = request.form.get('nome')
            usuario.email = request.form.get('email')
            usuario.perfil = perfil
            usuario.ativo = request.form.get('ativo') == 'on'
            
            nova_senha = request.form.get('senha')
            if nova_senha:
                usuario.set_senha(nova_senha)
            criar_perfil_operador(usuario)
            
            db.session.commit()
            return resposta_usuarios('Usuário atualizado com sucesso!')
        except Exception as e:
            db.session.rollback()
            return resposta_usuarios(f'Erro ao atualizar usuário: {str(e)}', False, 400)
    
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/usuarios/<int:id>/toggle', methods=['POST'])
@login_required
@permissao_requerida('gerenciar_usuarios')
def toggle_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    
    if not pode_gerenciar_usuario(usuario):
        return resposta_usuarios('Você não pode alterar este usuário.', False, 403)
    
    usuario.ativo = not usuario.ativo
    db.session.commit()
    
    status = 'ativado' if usuario.ativo else 'desativado'
    return resposta_usuarios(f'Usuário {status} com sucesso!')


@auth_bp.route('/usuarios/<int:id>/redefinir-senha', methods=['POST'])
@login_required
@permissao_requerida('gerenciar_usuarios')
def redefinir_senha_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if not pode_gerenciar_usuario(usuario):
        return resposta_usuarios('Você não pode redefinir a senha deste usuário.', False, 403)
    nova_senha = (request.form.get('senha') or '').strip()
    if len(nova_senha) < 6:
        return resposta_usuarios('A nova senha deve ter pelo menos 6 caracteres.', False, 400)
    usuario.set_senha(nova_senha)
    db.session.commit()
    return resposta_usuarios('Senha redefinida com sucesso.')


@auth_bp.route('/usuarios/<int:id>/delete', methods=['POST'])
@login_required
@permissao_requerida('gerenciar_usuarios')
def deletar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    
    if not pode_gerenciar_usuario(usuario):
        return resposta_usuarios('Você não pode excluir este usuário.', False, 403)
    
    try:
        db.session.delete(usuario)
        db.session.commit()
        return resposta_usuarios('Usuário excluído com sucesso!')
    except Exception as e:
        db.session.rollback()
        return resposta_usuarios(f'Erro ao deletar usuário: {str(e)}', False, 400)
