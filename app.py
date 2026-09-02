"""Application factory do PCP Industrial."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from sqlalchemy import text

from backend.apontamentos import apontamentos_bp
from backend.auth import auth_bp
from backend.cadastros import cadastros_bp
from backend.commands import init_commands
from backend.dashboard import dashboard_bp
from backend.estoque import estoque_bp
from backend.models import Usuario, db
from backend.ordens import ordens_bp
from backend.produtos import produtos_bp
from backend.relatorios import relatorios_bp
from backend.security import init_security
from config import get_config

migrate = Migrate()
login_manager = LoginManager()


def criar_app(config_name=None, config_overrides=None):
    raiz = Path(__file__).resolve().parent
    app = Flask(__name__, template_folder=str(raiz / "templates"), static_folder=str(raiz / "static"), instance_path=str(raiz / "instance"))
    app.config.from_object(get_config(config_name))
    if config_overrides:
        app.config.update(config_overrides)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Por favor, faça login para acessar esta página."
    login_manager.login_message_category = "warning"
    init_security(app)
    init_commands(app)
    _configure_logging(app)
    for blueprint in (auth_bp, dashboard_bp, cadastros_bp, produtos_bp, ordens_bp, apontamentos_bp, estoque_bp, relatorios_bp):
        app.register_blueprint(blueprint)

    @app.template_filter("g")
    def formato_compacto(valor):
        try:
            return format(float(valor), "g")
        except (TypeError, ValueError):
            return ""

    @app.template_filter("medida")
    def formato_medida(valor, unidade=""):
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return "—"
        exibicao = f"{numero:,.4f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
        siglas = {"UN": "un.", "DZ": "dz", "KG": "kg", "G": "g", "MG": "mg", "L": "L", "ML": "ml", "M": "m", "CM": "cm", "MM": "mm"}
        return f"{exibicao} {siglas.get(unidade, unidade or '')}".strip()

    @app.context_processor
    def globals_template():
        return {"current_user": current_user, "app_version": app.config["APP_VERSION"]}

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index" if current_user.is_authenticated else "auth.login"))

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(status="ok", database="connected", version=app.config["APP_VERSION"])
        except Exception:
            app.logger.exception("Falha no health check do banco")
            return jsonify(status="error", database="unavailable", version=app.config["APP_VERSION"]), 503

    _register_error_handlers(app)
    if app.config.get("AUTO_CREATE_DB"):
        with app.app_context():
            db.create_all()
    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


def _configure_logging(app):
    if app.testing:
        return
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if app.config.get("ENV_NAME") == "production":
        handler = logging.StreamHandler()
    else:
        log_dir = Path(app.instance_path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_error_handlers(app):
    for code in (400, 401, 403, 404, 405, 500):
        def handler(error, status_code=code):
            if status_code == 500:
                db.session.rollback()
                app.logger.error("Erro interno: %s", error)
            message = getattr(error, "description", "Erro interno")
            if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
                return jsonify(error=status_code, message=message), status_code
            return render_template("error.html", code=status_code, message=message), status_code
        app.register_error_handler(code, handler)


app = criar_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.debug)
