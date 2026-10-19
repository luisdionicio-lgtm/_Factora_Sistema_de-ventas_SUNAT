import pytest
from concurrent.futures import ThreadPoolExecutor
from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


def account(app, email="owner@example.com"):
    client = app.test_client()
    r = client.post(
        "/api/register",
        json={
            "name": "Luis",
            "company": "Negocio de prueba",
            "email": email,
            "password": "Password-test-123",
        },
    )
    assert r.status_code == 200
    csrf = client.get("/api/me").json["csrf"]
    return client, {"X-CSRF-Token": csrf}


def product(c, h, stock=10, price="118.00"):
    r = c.post(
        "/api/products",
        headers=h,
        json={
            "sku": "SKU1",
            "name": "Producto A",
            "category": "General",
            "price": price,
            "cost": "60.00",
            "stock": stock,
            "minimum": 3,
        },
    )
    assert r.status_code == 201, r.json
    return r.json["id"]


def sale(pid, qty=1, key="request-1", **extra):
    return {
        "kind": "boleta",
        "payment": "Efectivo",
        "items": [{"product_id": pid, "quantity": qty}],
        "request_key": key,
        **extra,
    }


def test_auth_csrf_and_origin(app):
    c, h = account(app)
    assert app.test_client().get("/api/products").status_code == 401
    assert c.post("/api/products", json={}).status_code == 403
    assert (
        c.post(
            "/api/products", headers={**h, "Origin": "https://evil.example"}, json={}
        ).status_code
        == 403
    )
    assert (
        "HttpOnly"
        in c.post(
            "/api/login",
            json={"email": "owner@example.com", "password": "Password-test-123"},
        ).headers["Set-Cookie"]
    )


def test_sale_totals_stock_and_idempotency(app):
    c, h = account(app)
    pid = product(c, h)
    payload = sale(pid, 2)
    payload["total"] = 1
    a = c.post("/api/sales", headers=h, json=payload)
    assert a.status_code == 201
    b = c.post("/api/sales", headers=h, json=payload)
    assert a.json == b.json
    s = c.get("/api/sales/" + str(a.json["id"])).json
    assert (s["total"], s["subtotal"], s["tax"]) == (23600, 20000, 3600)
    assert s["fiscal_status"] == "NO_EMITIDO"
    assert c.get("/api/products").json[0]["stock"] == 8
    assert len(c.get("/api/sales").json) == 1


def test_failed_sale_rolls_back(app):
    c, h = account(app)
    pid = product(c, h, 2)
    assert c.post("/api/sales", headers=h, json=sale(pid, 3)).status_code == 409
    assert c.get("/api/products").json[0]["stock"] == 2
    assert c.get("/api/sales").json == []
    assert (
        c.post("/api/sales", headers=h, json=sale(pid, 1, "retry")).status_code == 201
    )
    assert c.get("/api/sales").json[0]["number"] == "BF01-00000001"


def test_cancel_restores_stock_once(app):
    c, h = account(app)
    pid = product(c, h)
    sid = c.post("/api/sales", headers=h, json=sale(pid, 2)).json["id"]
    for _ in range(2):
        assert c.post(f"/api/sales/{sid}/cancel", headers=h, json={}).status_code == 200
    assert c.get("/api/products").json[0]["stock"] == 10
    assert c.get("/api/dashboard").json["stats"]["total"] == 0
    assert len(c.get("/api/movements").json) == 3


def test_tenant_isolation(app):
    a, ha = account(app)
    b, hb = account(app, "second@example.com")
    pid = product(a, ha)
    sid = a.post("/api/sales", headers=ha, json=sale(pid)).json["id"]
    assert b.get("/api/products").json == []
    assert b.get(f"/api/sales/{sid}").status_code == 404
    assert b.get(f"/receipt/{sid}").status_code == 404
    assert b.post(f"/api/sales/{sid}/cancel", headers=hb, json={}).status_code == 404
    assert b.post("/api/sales", headers=hb, json=sale(pid)).status_code == 400
    assert (
        b.post(
            f"/api/products/{pid}/stock",
            headers=hb,
            json={"delta": 1, "reason": "test"},
        ).status_code
        == 404
    )


def test_seller_permissions(app):
    c, h = account(app)
    pid = product(c, h)
    assert (
        c.post(
            "/api/users",
            headers=h,
            json={
                "name": "Vendedor",
                "email": "seller@example.com",
                "password": "Password-test-123",
                "role": "seller",
            },
        ).status_code
        == 201
    )
    s = app.test_client()
    s.post(
        "/api/login",
        json={"email": "seller@example.com", "password": "Password-test-123"},
    )
    hs = {"X-CSRF-Token": s.get("/api/me").json["csrf"]}
    assert s.post("/api/products", headers=hs, json={}).status_code == 403
    assert s.get("/api/users").status_code == 403
    assert s.put("/api/company", headers=hs, json={}).status_code == 403
    assert s.get("/api/export/products").status_code == 403
    assert s.post("/api/sales", headers=hs, json=sale(pid)).status_code == 201


def test_invoice_requires_ruc_customer(app):
    c, h = account(app)
    pid = product(c, h)
    assert (
        c.post("/api/sales", headers=h, json=sale(pid, kind="factura")).status_code
        == 400
    )
    cid = c.post(
        "/api/customers",
        headers=h,
        json={
            "name": "Empresa ficticia",
            "doc_type": "RUC",
            "document": "20000000001",
            "email": "",
            "address": "",
        },
    ).json["id"]
    assert (
        c.post(
            "/api/sales", headers=h, json=sale(pid, kind="factura", customer_id=cid)
        ).status_code
        == 201
    )
    assert c.get("/api/sales").json[0]["number"] == "FF01-00000001"


def test_product_validation(app):
    c, h = account(app)
    for price in ["NaN", "Infinity", "1.001", "-1"]:
        assert (
            c.post(
                "/api/products",
                headers=h,
                json={
                    "sku": "X",
                    "name": "X",
                    "category": "X",
                    "price": price,
                    "stock": 1,
                },
            ).status_code
            == 400
        )
    pid = product(c, h, 0)
    assert (
        c.post(
            f"/api/products/{pid}/stock",
            headers=h,
            json={"delta": -1, "reason": "Salida"},
        ).status_code
        == 409
    )
    assert c.post("/api/sales", headers=h, json=sale(pid, True)).status_code == 400


def test_snapshot_and_receipt_escape(app):
    c, h = account(app)
    pid = product(c, h)
    cid = c.post(
        "/api/customers",
        headers=h,
        json={
            "name": "<script>alert(1)</script>",
            "doc_type": "DNI",
            "document": "12345678",
        },
    ).json["id"]
    sid = c.post("/api/sales", headers=h, json=sale(pid, customer_id=cid)).json["id"]
    c.put(
        "/api/customers/" + str(cid),
        headers=h,
        json={"name": "Cambiado", "doc_type": "DNI", "document": "12345678"},
    )
    html = c.get("/receipt/" + str(sid)).text
    assert "&lt;script&gt;" in html and "<script>alert" not in html
    assert "SIN VALIDEZ TRIBUTARIA" in html
    assert "ticket.css" in c.get(f"/receipt/{sid}?format=ticket").text


def test_concurrent_stock_and_sequences(app):
    c, h = account(app)
    pid = product(c, h, 1)
    cookie = c.get_cookie("factora_session").value

    def buy(i):
        x = app.test_client()
        x.set_cookie("factora_session", cookie)
        return x.post(
            "/api/sales", headers=h, json=sale(pid, key=f"concurrent-{i}")
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(buy, range(2)))
    assert sorted(results) == [201, 409]
    assert c.get("/api/products").json[0]["stock"] == 0
    assert len(c.get("/api/sales").json) == 1


def test_archive_and_negative_stock(app):
    c, h = account(app)
    pid = product(c, h, 1)
    assert c.delete(f"/api/products/{pid}", headers=h, json={}).status_code == 409
    c.post(
        f"/api/products/{pid}/stock", headers=h, json={"delta": -1, "reason": "Retiro"}
    )
    assert c.delete(f"/api/products/{pid}", headers=h, json={}).status_code == 200
    assert c.get("/api/products").json == []
    assert len(c.get("/api/movements").json) == 2


def test_user_deactivation_revokes_session(app):
    c, h = account(app)
    c.post(
        "/api/users",
        headers=h,
        json={
            "name": "Otro",
            "email": "other@example.com",
            "password": "Password-test-123",
            "role": "seller",
        },
    )
    other = app.test_client()
    other.post(
        "/api/login",
        json={"email": "other@example.com", "password": "Password-test-123"},
    )
    uid = next(
        u["id"] for u in c.get("/api/users").json if u["email"] == "other@example.com"
    )
    assert other.get("/api/me").status_code == 200
    c.post(f"/api/users/{uid}/toggle", headers=h, json={})
    assert other.get("/api/me").status_code == 401


def test_idempotency_rejects_changed_payload(app):
    c, h = account(app)
    pid = product(c, h)
    assert c.post("/api/sales", headers=h, json=sale(pid)).status_code == 201
    assert c.post("/api/sales", headers=h, json=sale(pid, 2)).status_code == 409
    assert c.get("/api/products").json[0]["stock"] == 9


def test_csv_formula_and_logout(app):
    c, h = account(app)
    c.post(
        "/api/products",
        headers=h,
        json={
            "sku": "=1+1",
            "name": "Prueba",
            "category": "X",
            "price": "1.00",
            "stock": 1,
        },
    )
    assert "'=1+1" in c.get("/api/export/products").text
    assert c.post("/api/logout", headers=h, json={}).status_code == 200
    assert c.get("/api/me").status_code == 401
