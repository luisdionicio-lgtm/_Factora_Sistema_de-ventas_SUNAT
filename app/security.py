import hashlib, secrets, time
from functools import wraps
from flask import request, g, abort
from .db import row, get_db


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def protect(admin=False):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            s = row(
                "SELECT s.*,u.company_id,u.role,u.name,u.email,u.active FROM sessions s JOIN users u ON u.id=s.user_id WHERE token=? AND expires>?",
                (
                    token_hash(request.cookies.get("factora_session", "")),
                    int(time.time()),
                ),
            )
            if not s or not s["active"]:
                abort(401, description="Inicia sesión para continuar.")
            g.user = s
            g.company = s["company_id"]
            if request.method not in ("GET", "HEAD") and not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", ""), s["csrf"]
            ):
                abort(
                    403,
                    description="Sesión de formulario inválida. Actualiza la página.",
                )
            if admin and s["role"] != "admin":
                abort(403, description="Esta operación requiere un administrador.")
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def rate_limit(key, maximum=10):
    now = int(time.time())
    db = get_db()
    db.execute("DELETE FROM attempts WHERE reset_at<?", (now,))
    db.execute(
        "INSERT INTO attempts(key,count,reset_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
        (key, now + 900),
    )
    if row("SELECT count FROM attempts WHERE key=?", (key,))["count"] > maximum:
        abort(429, description="Demasiados intentos. Vuelve a intentar en 15 minutos.")


def audit(action, detail):
    get_db().execute(
        "INSERT INTO audit(company_id,user_id,action,detail) VALUES(?,?,?,?)",
        (g.company, g.user["user_id"], action, detail),
    )
