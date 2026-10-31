import os, json, secrets, time, sqlite3, io, csv
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify, g, abort, render_template, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from .db import get_db, close_db, initialize, row, rows, Transaction
from .security import protect, token_hash, rate_limit, audit
from .services import text, integer, money, customer_fields, create_sale, cancel_sale


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get(
            "DATABASE_PATH", str(Path(__file__).parent.parent / "data" / "factora.db")
        ),
        MAX_CONTENT_LENGTH=256 * 1024,
        COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    )
    if config:
        app.config.update(config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        initialize()
        from .fiscal import initialize_fiscal
        initialize_fiscal()
    from .fiscal import bp as fiscal_blueprint
    app.register_blueprint(fiscal_blueprint)

    @app.before_request
    def check_origin():
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                abort(403)
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                abort(403, description="Origen de solicitud no permitido.")
            if not request.is_json:
                abort(415, description="Envía datos JSON.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if app.config["COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.path.startswith("/api") or request.path.startswith("/receipt"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.description), e.code

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity(e):
        return (
            jsonify(
                error="Ya existe un registro con estos datos o una relación impide la operación."
            ),
            409,
        )

    @app.errorhandler(Exception)
    def unexpected(e):
        app.logger.error("Unhandled error type: %s", type(e).__name__)
        return (
            jsonify(error="No se pudo completar la operación. Inténtalo nuevamente."),
            500,
        )

    def payload():
        d = request.get_json()
        if not isinstance(d, dict):
            abort(400, description="El formulario es inválido.")
        return d

    def login_response(user):
        previous = request.cookies.get("factora_session")
        if previous:
            get_db().execute("DELETE FROM sessions WHERE token=?", (token_hash(previous),))
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        get_db().execute("DELETE FROM sessions WHERE expires<?", (int(time.time()),))
        get_db().execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (token_hash(token), user["id"], csrf, int(time.time()) + 28800),
        )
        response = jsonify(ok=True)
        response.set_cookie(
            "factora_session",
            token,
            httponly=True,
            secure=app.config["COOKIE_SECURE"],
            samesite="Lax",
            max_age=28800,
        )
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/api/register")
    def register():
        rate_limit("register:" + str(request.remote_addr), 5)
        d = payload()
        email = text(d, "email").lower()
        password = text(d, "password", 200)
        if "@" not in email:
            abort(400, description="Correo inválido.")
        if len(password) < 12:
            abort(400, description="Utiliza una contraseña de al menos 12 caracteres.")
        with Transaction() as db:
            cid = db.execute(
                "INSERT INTO companies(name,email) VALUES(?,?)",
                (text(d, "company"), email),
            ).lastrowid
            uid = db.execute(
                "INSERT INTO users(company_id,name,email,password,role) VALUES(?,?,?,?,?)",
                (
                    cid,
                    text(d, "name"),
                    email,
                    generate_password_hash(password),
                    "admin",
                ),
            ).lastrowid
        return login_response({"id": uid})

    @app.post("/api/login")
    def login():
        d = payload()
        email = text(d, "email").lower()
        rate_limit("login-ip:" + str(request.remote_addr), 40)
        rate_limit("login-email:" + email, 10)
        user = row("SELECT * FROM users WHERE email=? AND active=1", (email,))
        password = text(d, "password", 200)
        if not user or not check_password_hash(user["password"], password):
            abort(401, description="Correo o contraseña incorrectos.")
        get_db().execute("DELETE FROM attempts WHERE key=?", ("login-email:" + email,))
        return login_response(user)

    @app.post("/api/logout")
    @protect()
    def logout():
        get_db().execute("DELETE FROM sessions WHERE token=?", (g.user["token"],))
        r = jsonify(ok=True)
        r.delete_cookie("factora_session")
        return r

    @app.get("/api/me")
    @protect()
    def me():
        return jsonify(
            user={k: g.user[k] for k in ("name", "email", "role")},
            csrf=g.user["csrf"],
            company=row("SELECT * FROM companies WHERE id=?", (g.company,)),
        )

    @app.get("/api/products")
    @protect()
    def products():
        return jsonify(
            rows(
                "SELECT * FROM products WHERE company_id=? AND active=1 ORDER BY name",
                (g.company,),
            )
        )

    @app.post("/api/products")
    @protect(admin=True)
    def add_product():
        d = payload()
        stock = integer(d.get("stock", 0), "Stock")
        with Transaction() as db:
            pid = db.execute(
                "INSERT INTO products(company_id,sku,name,category,price,cost,stock,minimum) VALUES(?,?,?,?,?,?,?,?)",
                (
                    g.company,
                    text(d, "sku", 40),
                    text(d, "name"),
                    text(d, "category", 60),
                    money(d.get("price")),
                    money(d.get("cost", 0)),
                    stock,
                    integer(d.get("minimum", 5), "Stock mínimo"),
                ),
            ).lastrowid
            db.execute(
                "INSERT INTO movements(company_id,product_id,user_id,delta,balance,reason) VALUES(?,?,?,?,?,?)",
                (g.company, pid, g.user["user_id"], stock, stock, "Stock inicial"),
            )
            audit("PRODUCTO_CREADO", str(pid))
        return jsonify(id=pid), 201

    @app.put("/api/products/<int:pid>")
    @protect(admin=True)
    def edit_product(pid):
        d = payload()
        with Transaction() as db:
            if not row(
                "SELECT id FROM products WHERE id=? AND company_id=? AND active=1",
                (pid, g.company),
            ):
                abort(404)
            db.execute(
                "UPDATE products SET sku=?,name=?,category=?,price=?,cost=?,minimum=? WHERE id=? AND company_id=?",
                (
                    text(d, "sku", 40),
                    text(d, "name"),
                    text(d, "category", 60),
                    money(d.get("price")),
                    money(d.get("cost", 0)),
                    integer(d.get("minimum", 5), "Stock mínimo"),
                    pid,
                    g.company,
                ),
            )
            audit("PRODUCTO_EDITADO", str(pid))
        return jsonify(ok=True)

    @app.delete("/api/products/<int:pid>")
    @protect(admin=True)
    def archive_product(pid):
        with Transaction() as db:
            p = row(
                "SELECT * FROM products WHERE id=? AND company_id=? AND active=1",
                (pid, g.company),
            )
            if not p:
                abort(404)
            if p["stock"] != 0:
                abort(
                    409,
                    description="El producto debe tener stock cero para archivarlo.",
                )
            db.execute("UPDATE products SET active=0 WHERE id=?", (pid,))
            audit("PRODUCTO_ARCHIVADO", str(pid))
        return jsonify(ok=True)

    @app.post("/api/products/<int:pid>/stock")
    @protect(admin=True)
    def adjust_stock(pid):
        d = payload()
        delta = integer(d.get("delta"), "Movimiento", -1000000, 1000000)
        if delta == 0:
            abort(400, description="La cantidad no puede ser cero.")
        with Transaction() as db:
            p = row(
                "SELECT * FROM products WHERE id=? AND company_id=? AND active=1",
                (pid, g.company),
            )
            if not p:
                abort(404)
            balance = p["stock"] + delta
            if balance < 0:
                abort(409, description="El movimiento dejaría stock negativo.")
            db.execute("UPDATE products SET stock=? WHERE id=?", (balance, pid))
            db.execute(
                "INSERT INTO movements(company_id,product_id,user_id,delta,balance,reason) VALUES(?,?,?,?,?,?)",
                (
                    g.company,
                    pid,
                    g.user["user_id"],
                    delta,
                    balance,
                    text(d, "reason", 250),
                ),
            )
            audit("AJUSTE_STOCK", f"{pid}: {delta}")
        return jsonify(ok=True)

    @app.get("/api/customers")
    @protect()
    def customers():
        return jsonify(
            rows(
                "SELECT * FROM customers WHERE company_id=? ORDER BY name", (g.company,)
            )
        )

    @app.post("/api/customers")
    @protect()
    def add_customer():
        with Transaction() as db:
            cid = db.execute(
                "INSERT INTO customers(company_id,name,doc_type,document,email,address) VALUES(?,?,?,?,?,?)",
                (g.company, *customer_fields(payload())),
            ).lastrowid
            audit("CLIENTE_CREADO", str(cid))
        return jsonify(id=cid), 201

    @app.put("/api/customers/<int:cid>")
    @protect()
    def edit_customer(cid):
        with Transaction() as db:
            if not row(
                "SELECT id FROM customers WHERE id=? AND company_id=?", (cid, g.company)
            ):
                abort(404)
            db.execute(
                "UPDATE customers SET name=?,doc_type=?,document=?,email=?,address=? WHERE id=? AND company_id=?",
                (*customer_fields(payload()), cid, g.company),
            )
            audit("CLIENTE_EDITADO", str(cid))
        return jsonify(ok=True)

    @app.get("/api/sales")
    @protect()
    def sales():
        return jsonify(
            rows(
                "SELECT id,number,kind,total,subtotal,tax,payment,status,fiscal_status,created_at,customer_snapshot FROM sales WHERE company_id=? ORDER BY id DESC LIMIT 1000",
                (g.company,),
            )
        )

    @app.post("/api/sales")
    @protect()
    def sell():
        return jsonify(id=create_sale(payload())), 201

    @app.post("/api/sales/<int:sid>/cancel")
    @protect(admin=True)
    def cancel(sid):
        cancel_sale(sid)
        return jsonify(ok=True)

    @app.get("/api/sales/<int:sid>")
    @protect()
    def detail(sid):
        s = row("SELECT * FROM sales WHERE id=? AND company_id=?", (sid, g.company))
        if not s:
            abort(404)
        s["items"] = rows("SELECT * FROM sale_items WHERE sale_id=?", (sid,))
        return jsonify(s)

    @app.get("/receipt/<int:sid>")
    @protect()
    def receipt(sid):
        s = row("SELECT * FROM sales WHERE id=? AND company_id=?", (sid, g.company))
        if not s:
            abort(404)
        return render_template(
            "receipt.html",
            sale=s,
            company=json.loads(s["company_snapshot"]),
            customer=json.loads(s["customer_snapshot"]),
            items=rows("SELECT * FROM sale_items WHERE sale_id=?", (sid,)),
            ticket=request.args.get("format") == "ticket",
            local_date=(
                datetime.fromisoformat(s["created_at"]) - timedelta(hours=5)
            ).strftime("%d/%m/%Y · %H:%M"),
        )

    @app.get("/api/movements")
    @protect()
    def movements():
        return jsonify(
            rows(
                "SELECT m.*,p.name,p.sku,u.name AS operator FROM movements m JOIN products p ON p.id=m.product_id JOIN users u ON u.id=m.user_id WHERE m.company_id=? ORDER BY m.id DESC LIMIT 1000",
                (g.company,),
            )
        )

    @app.get("/api/dashboard")
    @protect()
    def dashboard():
        stats = row(
            "SELECT COALESCE(SUM(total),0) total,COUNT(*) count,COALESCE(SUM(CASE WHEN date(created_at,'-5 hours')=date('now','-5 hours') THEN total ELSE 0 END),0) today FROM sales WHERE company_id=? AND status='registrado'",
            (g.company,),
        )
        stats.update(
            row(
                "SELECT COUNT(*) products,COALESCE(SUM(cost*stock),0) value,COALESCE(SUM(stock<=minimum),0) low FROM products WHERE company_id=? AND active=1",
                (g.company,),
            )
        )
        trend = rows(
            "SELECT date(created_at,'-5 hours') day,SUM(total) total FROM sales WHERE company_id=? AND status='registrado' AND date(created_at,'-5 hours')>=date('now','-5 hours','-6 days') GROUP BY day ORDER BY day",
            (g.company,),
        )
        top = rows(
            "SELECT i.name,SUM(i.quantity) quantity,SUM(i.total) total FROM sale_items i JOIN sales s ON s.id=i.sale_id WHERE s.company_id=? AND s.status='registrado' GROUP BY i.product_id ORDER BY total DESC LIMIT 5",
            (g.company,),
        )
        return jsonify(stats=stats, trend=trend, top=top)

    @app.put("/api/company")
    @protect(admin=True)
    def company():
        d = payload()
        ruc = text(d, "ruc", 11, False)
        linked = row("SELECT ruc FROM fiscal_accounts WHERE company_id=?", (g.company,))
        if linked and ruc != linked["ruc"]:
            abort(409, description="El RUC está vinculado al emisor electrónico y debe mantenerse igual al del proveedor.")
        if ruc and (not ruc.isdigit() or len(ruc) != 11):
            abort(400, description="El RUC debe tener 11 dígitos.")
        with Transaction() as db:
            db.execute(
                "UPDATE companies SET name=?,ruc=?,address=?,email=?,phone=? WHERE id=?",
                (
                    text(d, "name"),
                    ruc,
                    text(d, "address", 250, False),
                    text(d, "email", 160, False),
                    text(d, "phone", 30, False),
                    g.company,
                ),
            )
            audit("EMPRESA_EDITADA", "Datos comerciales")
        return jsonify(ok=True)

    @app.get("/api/users")
    @protect(admin=True)
    def users():
        return jsonify(
            rows(
                "SELECT id,name,email,role,active FROM users WHERE company_id=?",
                (g.company,),
            )
        )

    @app.post("/api/users")
    @protect(admin=True)
    def add_user():
        d = payload()
        password = text(d, "password", 200)
        role = text(d, "role")
        email = text(d, "email").lower()
        if len(password) < 12 or role not in ("admin", "seller") or "@" not in email:
            abort(
                400,
                description="Revisa el correo, rol y contraseña (mínimo 12 caracteres).",
            )
        with Transaction() as db:
            db.execute(
                "INSERT INTO users(company_id,name,email,password,role) VALUES(?,?,?,?,?)",
                (
                    g.company,
                    text(d, "name"),
                    email,
                    generate_password_hash(password),
                    role,
                ),
            )
            audit("USUARIO_CREADO", email)
        return jsonify(ok=True), 201

    @app.post("/api/users/<int:uid>/toggle")
    @protect(admin=True)
    def toggle(uid):
        if uid == g.user["user_id"]:
            abort(400, description="No puedes desactivar tu propia cuenta.")
        with Transaction() as db:
            if not row(
                "SELECT id FROM users WHERE id=? AND company_id=?", (uid, g.company)
            ):
                abort(404)
            db.execute("UPDATE users SET active=1-active WHERE id=?", (uid,))
            db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
            audit("USUARIO_ESTADO", str(uid))
        return jsonify(ok=True)

    @app.put("/api/password")
    @protect()
    def password():
        d = payload()
        new = text(d, "new_password", 200)
        u = row("SELECT * FROM users WHERE id=?", (g.user["user_id"],))
        if (
            not check_password_hash(u["password"], text(d, "current_password", 200))
            or len(new) < 12
        ):
            abort(
                400,
                description="Contraseña actual incorrecta o nueva contraseña demasiado corta.",
            )
        with Transaction() as db:
            db.execute(
                "UPDATE users SET password=? WHERE id=?",
                (generate_password_hash(new), u["id"]),
            )
            db.execute(
                "DELETE FROM sessions WHERE user_id=? AND token!=?",
                (u["id"], g.user["token"]),
            )
            audit("CAMBIO_PASSWORD", "Sesiones adicionales revocadas")
        return jsonify(ok=True)

    @app.get("/api/audit")
    @protect(admin=True)
    def audits():
        return jsonify(
            rows(
                "SELECT a.*,u.name FROM audit a JOIN users u ON u.id=a.user_id WHERE a.company_id=? ORDER BY a.id DESC LIMIT 500",
                (g.company,),
            )
        )

    @app.post("/api/demo")
    @protect(admin=True)
    def demo():
        with Transaction() as db:
            if row("SELECT id FROM products WHERE company_id=? LIMIT 1", (g.company,)):
                abort(
                    409,
                    description="Los ejemplos solo se cargan en un inventario vacío.",
                )
            data = [
                ("TEC-001", "Teclado mecánico K68", "Tecnología", 18900, 12000, 24, 5),
                ("TEC-002", "Mouse inalámbrico M350", "Tecnología", 7900, 4200, 38, 8),
                ("TEC-003", "Audífonos Studio Pro", "Audio", 24900, 15800, 4, 5),
                ("ACC-001", "Hub USB-C · 6 puertos", "Accesorios", 12900, 8000, 16, 4),
                ("ACC-002", "Soporte para laptop", "Accesorios", 8900, 4500, 3, 5),
                (
                    "TEC-004",
                    "Monitor IPS 24 pulgadas",
                    "Tecnología",
                    59900,
                    43000,
                    12,
                    3,
                ),
                ("ACC-003", "Mousepad XL", "Accesorios", 3900, 1800, 45, 10),
                ("AUD-002", "Parlante portátil Mini", "Audio", 11900, 6900, 20, 4),
            ]
            for p in data:
                pid = db.execute(
                    "INSERT INTO products(company_id,sku,name,category,price,cost,stock,minimum) VALUES(?,?,?,?,?,?,?,?)",
                    (g.company, *p),
                ).lastrowid
                db.execute(
                    "INSERT INTO movements(company_id,product_id,user_id,delta,balance,reason) VALUES(?,?,?,?,?,?)",
                    (
                        g.company,
                        pid,
                        g.user["user_id"],
                        p[5],
                        p[5],
                        "Carga de ejemplos",
                    ),
                )
            audit("DEMO", "8 productos de ejemplo")
        return jsonify(ok=True)

    @app.get("/api/export/<kind>")
    @protect(admin=True)
    def export(kind):
        if kind == "products":
            records = rows(
                "SELECT sku,name,category,price,cost,stock,minimum FROM products WHERE company_id=? AND active=1",
                (g.company,),
            )
            fields = ["sku", "name", "category", "price", "cost", "stock", "minimum"]
        elif kind == "sales":
            records = rows(
                "SELECT number,kind,created_at,subtotal,tax,total,payment,status,fiscal_status FROM sales WHERE company_id=? ORDER BY id DESC",
                (g.company,),
            )
            fields = [
                "number",
                "kind",
                "created_at",
                "subtotal",
                "tax",
                "total",
                "payment",
                "status",
                "fiscal_status",
            ]
        else:
            abort(404)
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(fields)
        for record in records:
            vals = []
            for key in fields:
                v = record[key]
                if key in ("price", "cost", "total", "tax", "subtotal"):
                    v = f"{v/100:.2f}"
                if isinstance(v, str) and v.lstrip().startswith(
                    ("=", "+", "-", "@", "\t", "\r")
                ):
                    v = "'" + v
                vals.append(v)
            writer.writerow(vals)
        return Response(
            "\ufeff" + stream.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="factora-{kind}.csv"'
            },
        )

    return app
