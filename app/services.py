import json, re, hashlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import abort, g
from .db import row, rows, Transaction
from .security import audit


def text(data, key, limit=160, required=True):
    value = data.get(key, "")
    if (
        not isinstance(value, str)
        or len(value.strip()) > limit
        or (required and not value.strip())
    ):
        abort(400, description=f"Campo inválido: {key}.")
    return value.strip()


def integer(value, label, minimum=0, maximum=1000000):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        abort(
            400, description=f"{label}: ingresa un entero entre {minimum} y {maximum}."
        )
    return value


def money(value):
    try:
        amount = Decimal(str(value))
        if (
            not amount.is_finite()
            or amount < 0
            or amount > Decimal("1000000")
            or amount != amount.quantize(Decimal(".01"))
        ):
            raise ValueError()
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        abort(400, description="Importe inválido. Utiliza hasta dos decimales.")


def customer_fields(d):
    kind = text(d, "doc_type")
    document = text(d, "document", 30)
    if kind not in ("DNI", "RUC", "OTRO"):
        abort(400, description="Tipo de documento inválido.")
    if kind in ("DNI", "RUC") and not re.fullmatch(
        r"\d{" + ("8" if kind == "DNI" else "11") + r"}", document
    ):
        abort(400, description="El DNI debe tener 8 dígitos y el RUC 11.")
    return (
        text(d, "name"),
        kind,
        document,
        text(d, "email", 160, False),
        text(d, "address", 250, False),
    )


def create_sale(d):
    key = text(d, "request_key", 80)
    request_hash = hashlib.sha256(
        json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with Transaction() as db:
        existing = row(
            "SELECT id,request_hash FROM sales WHERE company_id=? AND request_key=?",
            (g.company, key),
        )
        if existing:
            if existing["request_hash"] != request_hash:
                abort(
                    409,
                    description="La clave de esta operación ya se usó con otro contenido. Limpia el carrito e inicia una nueva venta.",
                )
            return existing["id"]
        kind = text(d, "kind")
        if kind not in ("factura", "boleta"):
            abort(400, description="Selecciona factura o boleta.")
        payment = text(d, "payment")
        if payment not in ("Efectivo", "Yape", "Plin", "Tarjeta", "Transferencia"):
            abort(400, description="Medio de pago inválido.")
        customer = None
        if d.get("customer_id"):
            customer = row(
                "SELECT * FROM customers WHERE id=? AND company_id=?",
                (integer(d["customer_id"], "Cliente", 1), g.company),
            )
            if not customer:
                abort(400, description="Cliente no encontrado.")
        if kind == "factura" and (not customer or customer["doc_type"] != "RUC"):
            abort(400, description="La factura requiere un cliente con RUC.")
        items = d.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            abort(400, description="Agrega entre 1 y 100 productos.")
        grouped = {}
        for item in items:
            if not isinstance(item, dict):
                abort(400, description="Detalle inválido.")
            pid = integer(item.get("product_id"), "Producto", 1)
            grouped[pid] = grouped.get(pid, 0) + integer(
                item.get("quantity"), "Cantidad", 1, 100000
            )
        lines = []
        total = 0
        for pid, qty in grouped.items():
            p = row(
                "SELECT * FROM products WHERE id=? AND company_id=? AND active=1",
                (pid, g.company),
            )
            if not p:
                abort(400, description="Uno de los productos ya no está disponible.")
            if p["stock"] < qty:
                abort(
                    409,
                    description=f'Stock insuficiente para {p["name"]}. Disponible: {p["stock"]}.',
                )
            total += p["price"] * qty
            lines.append((p, qty))
        if total <= 0:
            abort(400, description="El total de la venta debe ser mayor a cero.")
        if total > 70000 and (not customer or customer["doc_type"] == "OTRO"):
            abort(
                400, description="Para esta venta identifica al cliente con DNI o RUC."
            )
        subtotal = int(
            (Decimal(total) / Decimal("1.18")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        db.execute(
            "INSERT OR IGNORE INTO sequences(company_id,kind,value) VALUES(?,?,0)",
            (g.company, kind),
        )
        db.execute(
            "UPDATE sequences SET value=value+1 WHERE company_id=? AND kind=?",
            (g.company, kind),
        )
        seq = row(
            "SELECT value FROM sequences WHERE company_id=? AND kind=?",
            (g.company, kind),
        )["value"]
        number = ("BF01" if kind == "boleta" else "FF01") + f"-{seq:08d}"
        company = row("SELECT * FROM companies WHERE id=?", (g.company,))
        sid = db.execute(
            "INSERT INTO sales(company_id,user_id,customer_id,customer_snapshot,company_snapshot,kind,number,subtotal,tax,total,payment,request_key,request_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                g.company,
                g.user["user_id"],
                customer["id"] if customer else None,
                json.dumps(
                    customer or {"name": "Consumidor final", "document": "—"},
                    ensure_ascii=False,
                ),
                json.dumps(company, ensure_ascii=False),
                kind,
                number,
                subtotal,
                total - subtotal,
                total,
                payment,
                key,
                request_hash,
            ),
        ).lastrowid
        for p, qty in lines:
            db.execute(
                "INSERT INTO sale_items(sale_id,product_id,name,sku,quantity,price,cost,total) VALUES(?,?,?,?,?,?,?,?)",
                (
                    sid,
                    p["id"],
                    p["name"],
                    p["sku"],
                    qty,
                    p["price"],
                    p["cost"],
                    p["price"] * qty,
                ),
            )
            db.execute("UPDATE products SET stock=stock-? WHERE id=?", (qty, p["id"]))
            db.execute(
                "INSERT INTO movements(company_id,product_id,user_id,delta,balance,reason,sale_id) VALUES(?,?,?,?,?,?,?)",
                (
                    g.company,
                    p["id"],
                    g.user["user_id"],
                    -qty,
                    p["stock"] - qty,
                    "Venta " + number,
                    sid,
                ),
            )
        audit("VENTA", number)
        return sid


def cancel_sale(sid):
    with Transaction() as db:
        sale = row("SELECT * FROM sales WHERE id=? AND company_id=?", (sid, g.company))
        if not sale:
            abort(404)
        if sale["status"] == "anulado":
            return
        if sale["fiscal_status"] != "NO_EMITIDO":
            abort(
                409,
                description="Un documento fiscal necesita el procedimiento de corrección correspondiente.",
            )
        for item in rows("SELECT * FROM sale_items WHERE sale_id=?", (sid,)):
            db.execute(
                "UPDATE products SET stock=stock+? WHERE id=?",
                (item["quantity"], item["product_id"]),
            )
            balance = row(
                "SELECT stock FROM products WHERE id=?", (item["product_id"],)
            )["stock"]
            db.execute(
                "INSERT INTO movements(company_id,product_id,user_id,delta,balance,reason,sale_id) VALUES(?,?,?,?,?,?,?)",
                (
                    g.company,
                    item["product_id"],
                    g.user["user_id"],
                    item["quantity"],
                    balance,
                    "Anulación interna " + sale["number"],
                    sid,
                ),
            )
        db.execute("UPDATE sales SET status='anulado' WHERE id=?", (sid,))
        audit("ANULACION", sale["number"])
