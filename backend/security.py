"""Proteções HTTP sem acoplar regras de negócio aos templates."""

import hmac
import secrets

from flask import abort, current_app, request, session


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def init_security(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def protect_csrf():
        if not current_app.config.get("WTF_CSRF_ENABLED", True) or request.method in SAFE_METHODS:
            return None
        expected = session.get("_csrf_token")
        received = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not expected or not received or not hmac.compare_digest(expected, received):
            abort(400, description="Token CSRF ausente ou inválido.")
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(self), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'",
        )
        if current_app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
