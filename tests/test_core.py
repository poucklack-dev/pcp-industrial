import pytest

from backend.models import Estrutura, Produto, Usuario, db
from backend.produtos import validar_circular
from backend.services import calcular_necessidades_recursivo


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["database"] == "connected"


def test_bom_multinivel_com_perda(app):
    with app.app_context():
        mp = Produto(codigo="MP", descricao="Matéria", tipo="MP", unidade="KG")
        sa = Produto(codigo="SA", descricao="Semi", tipo="SA", unidade="UN")
        pa = Produto(codigo="PA", descricao="Acabado", tipo="PA", unidade="UN")
        db.session.add_all([mp, sa, pa])
        db.session.flush()
        db.session.add_all([
            Estrutura(produto_pai_id=pa.id, componente_id=sa.id, quantidade=1),
            Estrutura(produto_pai_id=sa.id, componente_id=mp.id, quantidade=2, perda_percentual=10),
        ])
        db.session.commit()
        resultado = calcular_necessidades_recursivo(pa.id, 100)
        assert resultado[sa.id]["quantidade"] == 100
        assert resultado[mp.id]["quantidade"] == pytest.approx(220)


def test_bom_circular_bloqueada(app):
    with app.app_context():
        a = Produto(codigo="A", descricao="A", tipo="PA", unidade="UN")
        b = Produto(codigo="B", descricao="B", tipo="SA", unidade="UN")
        db.session.add_all([a, b])
        db.session.flush()
        db.session.add(Estrutura(produto_pai_id=b.id, componente_id=a.id, quantidade=1))
        db.session.commit()
        assert validar_circular(a.id, b.id) is False


def test_usuario_sem_permissao_recebe_403(app, client):
    with app.app_context():
        user = Usuario(nome="Consulta", email="consulta@example.com", perfil="Operador", ativo=True)
        user.set_senha("segura123")
        db.session.add(user)
        db.session.commit()
    client.post("/auth/login", data={"email": "consulta@example.com", "senha": "segura123"})
    assert client.get("/produtos/").status_code == 403
