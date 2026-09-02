"""Comandos administrativos seguros e reproduzíveis."""

import os
from datetime import date

import click
from flask.cli import with_appcontext

from backend.models import Configuracao, Estrutura, Maquina, Operador, OrdemProducao, Produto, Usuario, db


def _usuario(nome, email, perfil, senha):
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario:
        return usuario
    usuario = Usuario(nome=nome, email=email, perfil=perfil, ativo=True)
    usuario.set_senha(senha)
    db.session.add(usuario)
    return usuario


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Cria tabelas apenas para demonstração local; produção usa migrations."""
    db.create_all()
    click.echo("Banco inicializado.")


@click.command("seed")
@click.option("--reset", is_flag=True, help="Limpa as tabelas antes de semear.")
@with_appcontext
def seed_command(reset=False):
    """Cria um cenário industrial fictício e idempotente."""
    if reset:
        db.drop_all()
        db.create_all()

    admin_password = os.getenv("ADMIN_PASSWORD", "Admin@123")
    admin = _usuario("Administrador Demo", os.getenv("ADMIN_EMAIL", "admin@example.com"), "Supervisor", admin_password)
    _usuario("Planejador PCP", "pcp@example.com", "Analista", "Pcp@12345")
    operador_user = _usuario("Operador Demo", "operador@example.com", "Operador", "Operador@123")
    db.session.flush()

    maquina = Maquina.query.filter_by(codigo="CNC-01").first() or Maquina(codigo="CNC-01", nome="Centro de usinagem", status="Ativo")
    db.session.add(maquina)
    operador = Operador.query.filter_by(codigo="OP-0001").first() or Operador(codigo="OP-0001", nome="Operador Demo", setor="Produção", status="Ativo", usuario_id=operador_user.id)
    db.session.add(operador)
    db.session.flush()

    dados = [
        ("MP-001", "Aço carbono", "MP", "KG", 800, 200),
        ("MP-002", "Tinta industrial", "MP", "L", 120, 30),
        ("SA-001", "Conjunto usinado", "SA", "UN", 40, 10),
        ("PA-001", "Produto acabado demo", "PA", "UN", 12, 5),
    ]
    produtos = {}
    for codigo, descricao, tipo, unidade, saldo, minimo in dados:
        produto = Produto.query.filter_by(codigo=codigo).first()
        if not produto:
            produto = Produto(codigo=codigo, descricao=descricao, tipo=tipo, unidade=unidade, estoque_atual=saldo, estoque_minimo=minimo, status="Ativo")
            db.session.add(produto)
        produtos[codigo] = produto
    db.session.flush()
    for pai, componente, quantidade in [("SA-001", "MP-001", 2.5), ("PA-001", "SA-001", 1), ("PA-001", "MP-002", 0.2)]:
        if not Estrutura.query.filter_by(produto_pai_id=produtos[pai].id, componente_id=produtos[componente].id).first():
            db.session.add(Estrutura(produto_pai_id=produtos[pai].id, componente_id=produtos[componente].id, quantidade=quantidade, unidade_consumo=produtos[componente].unidade))
    if not OrdemProducao.query.filter_by(numero="OP-DEMO-001").first():
        db.session.add(OrdemProducao(numero="OP-DEMO-001", produto_id=produtos["PA-001"].id, quantidade_planejada=50, data=date.today(), prioridade="Normal", status="Planejada"))
    if not Configuracao.query.first():
        db.session.add(Configuracao(permitir_estoque_negativo=False))
    db.session.commit()
    click.echo(f"Dados fictícios criados. Admin: {admin.email} (senha definida por ADMIN_PASSWORD).")


def init_commands(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
