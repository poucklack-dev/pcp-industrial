# backend/cadastros.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from backend.models import db, Maquina
from backend.auth import permissao_requerida

cadastros_bp = Blueprint('cadastros', __name__, url_prefix='/cadastros')


@cadastros_bp.route('/maquinas', methods=['GET', 'POST'])
@login_required
@permissao_requerida('ver_cadastros')
def maquinas():
    if request.method == 'POST':
        if current_user.perfil not in ('Supervisor', 'Analista'):
            flash('Somente Supervisores ou Analistas podem alterar máquinas.', 'danger')
            return redirect(url_for('cadastros.maquinas'))
        try:
            codigo = request.form['codigo'].strip()
            if Maquina.query.filter_by(codigo=codigo).first():
                flash('Código de máquina já existe.', 'danger')
                return render_template(
                    'maquinas.html',
                    maquinas=Maquina.query.order_by(Maquina.codigo).all()
                )
            
            maquina = Maquina(
                codigo=codigo,
                nome=request.form['nome'].strip(),
                descricao=request.form.get('descricao'),
                status=request.form.get('status', 'Ativo')
            )
            db.session.add(maquina)
            db.session.commit()
            flash(f'Máquina {maquina.nome} cadastrada com sucesso.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')
    
    return render_template(
        'maquinas.html',
        maquinas=Maquina.query.order_by(Maquina.codigo).all()
    )


@cadastros_bp.route('/maquinas/<int:id>/editar', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def editar_maquina(id):
    try:
        maquina = Maquina.query.get_or_404(id)
        maquina.codigo = request.form['codigo'].strip()
        maquina.nome = request.form['nome'].strip()
        maquina.descricao = request.form.get('descricao')
        maquina.status = request.form.get('status', 'Ativo')
        db.session.commit()
        flash(f'Máquina {maquina.nome} atualizada com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {e}', 'danger')
    
    return redirect(url_for('cadastros.maquinas'))


@cadastros_bp.route('/maquinas/<int:id>/toggle', methods=['POST'])
@login_required
@permissao_requerida('editar_op')
def toggle_maquina(id):
    try:
        maquina = Maquina.query.get_or_404(id)
        maquina.status = 'Inativo' if maquina.status == 'Ativo' else 'Ativo'
        db.session.commit()
        status = 'ativada' if maquina.status == 'Ativo' else 'desativada'
        flash(f'Máquina {maquina.nome} {status} com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {e}', 'danger')
    
    return redirect(url_for('cadastros.maquinas'))
