"""Configurações da aplicação, selecionadas por ``APP_ENV``/``FLASK_ENV``."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _database_url(default_name="pcp.db"):
    value = os.getenv("DATABASE_URL")
    if value:
        # Heroku e provedores antigos ainda entregam o prefixo descontinuado.
        return value.replace("postgres://", "postgresql://", 1)
    return f"sqlite:///{(BASE_DIR / 'instance' / default_name).as_posix()}"


class Config:
    ENV_NAME = "base"
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    AUTO_CREATE_DB = False


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "false").lower() == "true"


class TestingConfig(Config):
    ENV_NAME = "testing"
    TESTING = True
    SECRET_KEY = "testing-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    ENV_NAME = "production"
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name=None):
    environment = (name or os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "development").lower()
    config = CONFIGS.get(environment)
    if config is None:
        raise RuntimeError(f"Ambiente desconhecido: {environment}")
    if environment == "production" and not config.SECRET_KEY:
        raise RuntimeError("SECRET_KEY é obrigatória em produção.")
    return config
