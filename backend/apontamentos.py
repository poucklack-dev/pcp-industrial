# backend/apontamentos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from backend.models import db, OrdemProducao, Operador, Apontamento, Historico
from backend.auth import permissao_requerida
from backend.services import consumir_componentes, registrar_producao

apontamentos_bp = Blueprint('apontamentos', __name__, url_prefix='/apontamentos')


@apontamentos_bp.route('/')
@login_required
@permissao_requerida('ver_apontamentos')
def index():
    return render_template(
        'apontamentos.html',
        apontamentos=Apontamento.query.order_by(Apontamento.data_hora.desc()).all(),
        ops=OrdemProducao.query.filter(
            OrdemProducao.status.in_(['Liberada', 'Em produção', 'Pausada'])
        ).all(),
        operadores=(Operador.query.filter_by(usuario_id=current_user.id, status='Ativo').all()
                    if current_user.perfil == 'Operador' else Operador.query.filter_by(status='Ativo').all()),
        current_user=current_user
    )


@apontamentos_bp.route('/novo', methods=['POST'])
@login_required
@permissao_requerida('apontar_producao')
def novo():
    try:
        op = OrdemProducao.query.get_or_404(int(request.form['op_id']))
        if op.status in ('Cancelada', 'Concluída'):
            raise ValueError('Esta OP não pode receber apontamentos.')
        
        produzida = float(request.form['quantidade_produzida'])
        boa = float(request.form['quantidade_boa'])
        refugo = float(request.form['quantidade_refugada'] or 0)
        
        if produzida <= 0 or boa < 0 or refugo < 0:
            raise ValueError('Quantidades devem ser positivas.')
        
        if abs((boa + refugo) - produzida) > 0.000001:
            raise ValueError('Quantidade produzida deve ser igual a boa + refugo.')
        
        if op.quantidade_produzida + produzida > op.quantidade_planejada:
            raise ValueError('O apontamento ultrapassa a quantidade planejada da OP.')
        
        ap = Apontamento(
            op_id=op.id,
            operador_id=int(request.form['operador_id']) if request.form.get('operador_id') else None,
            quantidade_produzida=produzida,
            quantidade_boa=boa,
            quantidade_refugada=refugo,
            motivo_refugo=request.form.get('motivo_refugo'),
            observacao=request.form.get('observacao')
        )
        db.session.add(ap)
        db.session.flush()
        
        # Consumo proporcional à quantidade produzida
        consumir_componentes(op, produzida, ap.id)
        registrar_producao(op, boa, ap.id)
        
        op.quantidade_produzida += produzida
        if op.quantidade_produzida >= op.quantidade_planejada:
            op.status = 'Concluída'
        elif op.status in ('Liberada', 'Pausada'):
            op.status = 'Em produção'
        
        db.session.add(Historico(
            op_id=op.id,
            descricao=f'Apontamento de {produzida:g}; boa {boa:g}; refugo {refugo:g}. Usuário: {current_user.nome}'
        ))
        db.session.commit()
        flash('Apontamento registrado e estoque atualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Não foi possível registrar: {e}', 'danger')
    return redirect(url_for('apontamentos.index'))
