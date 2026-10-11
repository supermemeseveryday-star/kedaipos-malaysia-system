"""Scan-to-order, online payments, refunds and daily settlement for Kedai POS.

Customers scan a table's QR code, order without logging in and pay online. The
order only reaches the POS once the payment gateway confirms payment. Refunds
and the daily settlement read from the same `payments` and `refunds` tables,
so the accountant's figures are always live.

Payments go through a `Gateway`. `MockGateway` simulates an e-wallet/card
checkout for development; a real provider (Fiuu, Stripe, iPay88, ...)
implements the same three methods: `create`, `verify_webhook` and `refund`.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import secrets
import time
from datetime import datetime

# Payment methods. "online" ones are paid by the customer through the gateway.
METHODS = {
    "cash": {"label": "现金 Cash", "online": False},
    "qr": {"label": "DuitNow QR", "online": False},
    "tng": {"label": "Touch 'n Go eWallet", "online": True},
    "grabpay": {"label": "GrabPay", "online": True},
    "boost": {"label": "Boost", "online": True},
    "shopeepay": {"label": "ShopeePay", "online": True},
    "applepay": {"label": "Apple Pay", "online": True},
    "googlepay": {"label": "Google Pay", "online": True},
    "card": {"label": "Debit / Credit card", "online": True},
    "fpx": {"label": "FPX online banking", "online": True},
}
ONLINE_METHODS = [m for m, v in METHODS.items() if v["online"]]
CHECKOUT_TTL = 15 * 60
MAX_QTY = 50
QR_USERNAME = "__qr_customer__"


class OrderingError(ValueError):
    """A request the customer or staff can fix; `status` is the HTTP code to answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- schema

def migrate(db, now_iso, pass_hash) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS dining_tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS checkout_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL UNIQUE,
        table_id INTEGER NOT NULL REFERENCES dining_tables(id),
        items TEXT NOT NULL,
        subtotal_cents INTEGER NOT NULL,
        tax_cents INTEGER NOT NULL,
        total_cents INTEGER NOT NULL,
        method TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','paid','failed','refunded')),
        order_id INTEGER REFERENCES orders(id),
        message TEXT NOT NULL DEFAULT '',
        client_ip TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        expires_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES checkout_sessions(id),
        order_id INTEGER REFERENCES orders(id),
        provider TEXT NOT NULL,
        method TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        refunded_cents INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','succeeded','failed','refunded','partially_refunded')),
        provider_ref TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        payment_id INTEGER REFERENCES payments(id),
        amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
        method TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        restocked INTEGER NOT NULL DEFAULT 0,
        provider_ref TEXT NOT NULL DEFAULT '',
        created_by INTEGER REFERENCES users(id),
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS day_closings (
        day TEXT PRIMARY KEY,
        closed_at TEXT NOT NULL,
        closed_by INTEGER REFERENCES users(id),
        counted_cash_cents INTEGER NOT NULL,
        expected_cash_cents INTEGER NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        snapshot TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_refunds_created ON refunds(created_at);
    CREATE INDEX IF NOT EXISTS idx_orders_paid ON orders(paid_at);
    CREATE INDEX IF NOT EXISTS idx_sessions_status ON checkout_sessions(status, created_at);
    """)
    cols = {r[1] for r in db.execute("PRAGMA table_info(orders)")}
    for name, ddl in (("source", "TEXT NOT NULL DEFAULT 'pos'"),
                      ("table_id", "INTEGER REFERENCES dining_tables(id)"),
                      ("refunded_cents", "INTEGER NOT NULL DEFAULT 0")):
        if name not in cols:
            db.execute(f"ALTER TABLE orders ADD COLUMN {name} {ddl}")
    # Refunds recorded before the refunds table existed: keep them in the settlement.
    for o in db.execute("""SELECT id, total_cents, payment_method, refunded_at, refund_note FROM orders o
                           WHERE status='refunded' AND NOT EXISTS (SELECT 1 FROM refunds r WHERE r.order_id=o.id)""").fetchall():
        db.execute("INSERT INTO refunds(order_id,amount_cents,method,reason,restocked,created_at) VALUES(?,?,?,?,1,?)",
                   (o[0], o[1], o[2] or "cash", o[4] or "", o[3] or now_iso()))
        db.execute("UPDATE orders SET refunded_cents=total_cents WHERE id=?", (o[0],))
    # Orders placed by customers need a `created_by`; this account can never sign in.
    if not db.execute("SELECT 1 FROM users WHERE username=?", (QR_USERNAME,)).fetchone():
        db.execute("INSERT INTO users(username,display_name,role,password_hash,active,created_at) VALUES(?,?,'staff',?,0,?)",
                   (QR_USERNAME, "扫码顾客 QR customer", pass_hash(secrets.token_urlsafe(32)), now_iso()))


def qr_user_id(db) -> int:
    return db.execute("SELECT id FROM users WHERE username=?", (QR_USERNAME,)).fetchone()[0]


# ---------------------------------------------------------------- gateways

class MockGateway:
    """Simulated e-wallet/card gateway for development and demos.

    It behaves like a real hosted checkout: the customer is sent to a payment
    page, and the result comes back as an HMAC-signed webhook. No money moves.
    """
    name = "mock"
    test_mode = True

    def __init__(self, secret: str):
        self.secret = secret.encode()

    def create(self, session: dict) -> dict:
        ref = "mock_" + secrets.token_urlsafe(18)
        return {"provider_ref": ref, "redirect_url": f"/pay/mock?ref={ref}"}

    def sign(self, raw: bytes) -> str:
        return hmac.new(self.secret, raw, hashlib.sha256).hexdigest()

    def verify_webhook(self, headers, raw: bytes) -> dict:
        sent = headers.get("X-Mock-Signature", "")
        if not sent or not hmac.compare_digest(sent, self.sign(raw)):
            raise OrderingError("Invalid webhook signature", 401)
        event = json.loads(raw.decode("utf-8"))
        if event.get("status") not in ("succeeded", "failed"):
            raise OrderingError("Unknown payment status")
        return {"provider_ref": str(event.get("provider_ref", "")), "status": event["status"],
                "amount_cents": int(event.get("amount_cents", -1))}

    def refund(self, payment: dict, amount_cents: int) -> str:
        return "mockrf_" + secrets.token_urlsafe(12)


def gateway(db, setting) -> MockGateway:
    secret = setting(db, "mock_gateway_secret", "")
    if not secret:
        raise OrderingError("Payment gateway is not configured", 503)
    return MockGateway(secret)


def ensure_secrets(db, setting, set_setting) -> None:
    if not setting(db, "mock_gateway_secret", ""):
        set_setting(db, "mock_gateway_secret", secrets.token_hex(32))


# ---------------------------------------------------------------- tables

def create_table(db, name: str, now_iso) -> dict:
    name = name.strip()[:40]
    if not name:
        raise OrderingError("Table name is required")
    code = secrets.token_urlsafe(9)
    cur = db.execute("INSERT INTO dining_tables(name,code,created_at) VALUES(?,?,?)", (name, code, now_iso()))
    return {"id": cur.lastrowid, "name": name, "code": code, "active": 1}


def list_tables(db) -> list[dict]:
    return [dict(r) for r in db.execute("SELECT id,name,code,active,created_at FROM dining_tables ORDER BY id")]


def table_by_code(db, code: str):
    row = db.execute("SELECT * FROM dining_tables WHERE code=? AND active=1", (str(code or ""),)).fetchone()
    if not row:
        raise OrderingError("This table QR code is not active. Please ask the staff.", 404)
    return row


# ---------------------------------------------------------------- customer side

def ordering_enabled(db, setting) -> bool:
    return bool(setting(db, "qr_ordering_enabled", False))


def enabled_methods(db, setting) -> list[str]:
    chosen = setting(db, "qr_payment_methods", ONLINE_METHODS)
    return [m for m in ONLINE_METHODS if m in chosen]


def tax_rate(db, setting) -> float:
    try:
        return float(setting(db, "tax_rate", 0)) if setting(db, "tax_enabled", False) else 0.0
    except (TypeError, ValueError):
        return 0.0


def public_menu(db, setting, code: str) -> dict:
    if not ordering_enabled(db, setting):
        raise OrderingError("Scan-to-order is currently closed. Please order at the counter.", 403)
    table = table_by_code(db, code)
    products = [{"id": p["id"], "name": p["name"], "category": p["category"], "price_cents": p["price_cents"],
                 "image": p["image"], "sold_out": p["stock"] < 1}
                for p in db.execute("SELECT * FROM products WHERE active=1 ORDER BY category,name")]
    return {"shop": {"name": setting(db, "shop_name", "Kedai POS"), "address": setting(db, "shop_address", ""),
                     "phone": setting(db, "shop_phone", "")},
            "table": {"name": table["name"]}, "products": products,
            "tax": {"rate": tax_rate(db, setting), "label": setting(db, "tax_label", "Tax")},
            "methods": [{"id": m, "label": METHODS[m]["label"]} for m in enabled_methods(db, setting)],
            "test_mode": True}


def _price_items(db, items) -> tuple[list[dict], int]:
    if not isinstance(items, list) or not items:
        raise OrderingError("Your cart is empty")
    wanted: dict[int, int] = {}
    for item in items:
        try:
            pid, qty = int(item.get("product_id")), int(item.get("quantity"))
        except (AttributeError, TypeError, ValueError):
            raise OrderingError("Invalid cart item") from None
        if qty < 1 or qty > MAX_QTY:
            raise OrderingError(f"Quantity must be between 1 and {MAX_QTY}")
        wanted[pid] = wanted.get(pid, 0) + qty
    lines, subtotal = [], 0
    for pid, qty in wanted.items():
        p = db.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        if not p:
            raise OrderingError("An item in your cart is no longer available", 409)
        if p["stock"] < qty:
            raise OrderingError(f"Sorry, {p['name']} is sold out or not enough left", 409)
        line = p["price_cents"] * qty
        subtotal += line
        lines.append({"product_id": pid, "name": p["name"], "sku": p["sku"], "quantity": qty,
                      "unit_price_cents": p["price_cents"], "line_total_cents": line})
    return lines, subtotal


def create_checkout(db, setting, now_iso, body: dict, client_ip: str) -> dict:
    if not ordering_enabled(db, setting):
        raise OrderingError("Scan-to-order is currently closed. Please order at the counter.", 403)
    table = table_by_code(db, body.get("table"))
    method = str(body.get("method", ""))
    if method not in enabled_methods(db, setting):
        raise OrderingError("Please choose a payment method")
    db.execute("BEGIN IMMEDIATE")
    try:
        lines, subtotal = _price_items(db, body.get("items"))
        tax = round(subtotal * tax_rate(db, setting) / 100)
        token = secrets.token_urlsafe(24)
        cur = db.execute("""INSERT INTO checkout_sessions(token,table_id,items,subtotal_cents,tax_cents,total_cents,method,note,client_ip,created_at,expires_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                         (token, table["id"], json.dumps(lines, ensure_ascii=False), subtotal, tax, subtotal + tax, method,
                          str(body.get("note", ""))[:200], client_ip, now_iso(), time.time() + CHECKOUT_TTL))
        session = {"id": cur.lastrowid, "token": token, "total_cents": subtotal + tax, "method": method}
        gw = gateway(db, setting)
        created = gw.create(session)
        db.execute("INSERT INTO payments(session_id,provider,method,amount_cents,provider_ref,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                   (session["id"], gw.name, method, session["total_cents"], created["provider_ref"], now_iso(), now_iso()))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return {"session": token, "pay_url": created["redirect_url"], "total_cents": subtotal + tax}


def checkout_status(db, token: str) -> dict:
    s = db.execute("""SELECT s.*, t.name AS table_name, o.receipt_no, o.paid_at FROM checkout_sessions s
                      JOIN dining_tables t ON t.id=s.table_id LEFT JOIN orders o ON o.id=s.order_id WHERE s.token=?""",
                   (str(token or ""),)).fetchone()
    if not s:
        raise OrderingError("Order not found", 404)
    status = s["status"]
    if status == "pending" and s["expires_at"] < time.time():
        status = "expired"
    return {"status": status, "table": s["table_name"], "items": json.loads(s["items"]),
            "subtotal_cents": s["subtotal_cents"], "tax_cents": s["tax_cents"], "total_cents": s["total_cents"],
            "method": s["method"], "method_label": METHODS[s["method"]]["label"], "receipt_no": s["receipt_no"],
            "paid_at": s["paid_at"], "message": s["message"]}


def mock_payment_page(db, ref: str) -> dict:
    p = db.execute("""SELECT p.*, s.token, s.status AS session_status FROM payments p JOIN checkout_sessions s ON s.id=p.session_id
                      WHERE p.provider_ref=? AND p.provider='mock'""", (str(ref or ""),)).fetchone()
    if not p:
        raise OrderingError("Payment not found", 404)
    return {"amount_cents": p["amount_cents"], "method": p["method"], "method_label": METHODS[p["method"]]["label"],
            "status": p["status"], "session": p["token"]}


def mock_complete(db, setting, now_iso, audit, business_now, body: dict) -> dict:
    """The simulated payment page reports the customer's choice the way a real gateway would: a signed webhook."""
    ref = str(body.get("ref", ""))
    p = db.execute("SELECT amount_cents FROM payments WHERE provider_ref=? AND provider='mock'", (ref,)).fetchone()
    if not p:
        raise OrderingError("Payment not found", 404)
    raw = json.dumps({"provider_ref": ref, "status": "succeeded" if body.get("approve") else "failed",
                      "amount_cents": p[0]}).encode()
    gw = gateway(db, setting)
    return handle_webhook(db, setting, now_iso, audit, business_now, {"X-Mock-Signature": gw.sign(raw)}, raw)


def handle_webhook(db, setting, now_iso, audit, business_now, headers, raw: bytes) -> dict:
    gw = gateway(db, setting)
    event = gw.verify_webhook(headers, raw)
    db.execute("BEGIN IMMEDIATE")
    try:
        result = _apply_payment_event(db, setting, now_iso, audit, business_now, gw, event)
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return result


def _apply_payment_event(db, setting, now_iso, audit, business_now, gw, event) -> dict:
    p = db.execute("SELECT * FROM payments WHERE provider_ref=? AND provider=?", (event["provider_ref"], gw.name)).fetchone()
    if not p:
        raise OrderingError("Unknown payment", 404)
    s = db.execute("SELECT * FROM checkout_sessions WHERE id=?", (p["session_id"],)).fetchone()
    if p["status"] != "pending":  # gateways retry webhooks; answer the same way every time
        return {"ok": True, "status": s["status"], "duplicate": True}
    if event["status"] == "failed":
        db.execute("UPDATE payments SET status='failed',updated_at=? WHERE id=?", (now_iso(), p["id"]))
        db.execute("UPDATE checkout_sessions SET status='failed',message='Payment was not completed' WHERE id=?", (s["id"],))
        return {"ok": True, "status": "failed"}
    if event["amount_cents"] != p["amount_cents"]:
        raise OrderingError("Paid amount does not match the order", 409)
    db.execute("UPDATE payments SET status='succeeded',updated_at=? WHERE id=?", (now_iso(), p["id"]))
    lines = json.loads(s["items"])
    # The money is taken. If stock ran out since checkout, give it straight back instead of leaving an unfillable order.
    for line in lines:
        prod = db.execute("SELECT stock, active FROM products WHERE id=?", (line["product_id"],)).fetchone()
        if not prod or not prod["active"] or prod["stock"] < line["quantity"]:
            ref = gw.refund(dict(p), p["amount_cents"])
            db.execute("UPDATE payments SET status='refunded',refunded_cents=amount_cents,updated_at=? WHERE id=?", (now_iso(), p["id"]))
            db.execute("UPDATE checkout_sessions SET status='refunded',message=? WHERE id=?",
                       (f"{line['name']} sold out while you were paying. Your payment has been refunded. (ref {ref})", s["id"]))
            audit(db, None, "auto_refund", "checkout", s["id"], {"reason": "out_of_stock", "provider_ref": ref})
            return {"ok": True, "status": "refunded"}
    paid = now_iso()
    cur = db.execute("""INSERT INTO orders(created_by,cashier_id,subtotal_cents,tax_cents,total_cents,payment_method,payment_reference,
                        created_at,paid_at,status,note,source,table_id) VALUES(?,?,?,?,?,?,?,?,?,'paid',?,'qr',?)""",
                     (qr_user_id(db), None, s["subtotal_cents"], s["tax_cents"], s["total_cents"], s["method"], p["provider_ref"],
                      s["created_at"], paid, s["note"], s["table_id"]))
    oid = cur.lastrowid
    receipt = f"KED-{business_now().strftime('%y%m%d')}-{oid:05d}"
    db.execute("UPDATE orders SET receipt_no=? WHERE id=?", (receipt, oid))
    for line in lines:
        db.execute("""INSERT INTO order_items(order_id,product_id,product_name,sku,quantity,unit_price_cents,line_total_cents)
                      VALUES(?,?,?,?,?,?,?)""", (oid, line["product_id"], line["name"], line["sku"], line["quantity"],
                                                   line["unit_price_cents"], line["line_total_cents"]))
        db.execute("UPDATE products SET stock=stock-?,updated_at=? WHERE id=?", (line["quantity"], paid, line["product_id"]))
    db.execute("UPDATE payments SET order_id=? WHERE id=?", (oid, p["id"]))
    db.execute("UPDATE checkout_sessions SET status='paid',order_id=? WHERE id=?", (oid, s["id"]))
    audit(db, None, "settle", "order", oid, {"receipt": receipt, "method": s["method"], "source": "qr", "provider": gw.name})
    return {"ok": True, "status": "paid", "order_id": oid}


# ---------------------------------------------------------------- refunds

def refund_order(db, setting, now_iso, audit, order_id: int, user_id: int, body: dict) -> dict:
    """Full or partial refund. Online payments are refunded through the gateway; cash and DuitNow are recorded as handed back."""
    db.execute("BEGIN IMMEDIATE")
    try:
        o = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not o:
            raise OrderingError("Order not found", 404)
        if o["status"] not in ("paid", "refunded"):
            raise OrderingError("Only paid orders can be refunded", 409)
        remaining = o["total_cents"] - o["refunded_cents"]
        if remaining <= 0:
            raise OrderingError("This order has already been fully refunded", 409)
        raw_amount = body.get("amount")
        if raw_amount in (None, ""):
            amount = remaining
        else:
            try:
                amount = round(float(raw_amount) * 100)
            except (TypeError, ValueError):
                raise OrderingError("Refund amount must be a number") from None
        if amount <= 0 or amount > remaining:
            raise OrderingError(f"Refund amount must be between RM 0.01 and RM {remaining / 100:.2f}")
        reason = str(body.get("reason", body.get("note", ""))).strip()[:300]
        full = amount == remaining
        restock = bool(body.get("restock", full)) and full and o["refunded_cents"] == 0
        method = o["payment_method"] or "cash"
        payment, ref = None, ""
        if METHODS.get(method, {}).get("online"):
            payment = db.execute("SELECT * FROM payments WHERE order_id=? AND status IN ('succeeded','partially_refunded')", (order_id,)).fetchone()
            if not payment:
                raise OrderingError("The online payment for this order was not found", 409)
            ref = gateway(db, setting).refund(dict(payment), amount)
            refunded = payment["refunded_cents"] + amount
            db.execute("UPDATE payments SET refunded_cents=?,status=?,updated_at=? WHERE id=?",
                       (refunded, "refunded" if refunded >= payment["amount_cents"] else "partially_refunded", now_iso(), payment["id"]))
        when = now_iso()
        cur = db.execute("""INSERT INTO refunds(order_id,payment_id,amount_cents,method,reason,restocked,provider_ref,created_by,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?)""",
                         (order_id, payment["id"] if payment else None, amount, method, reason, int(restock), ref, user_id, when))
        total_refunded = o["refunded_cents"] + amount
        db.execute("UPDATE orders SET refunded_cents=?,status=?,refunded_at=?,refund_note=? WHERE id=?",
                   (total_refunded, "refunded" if total_refunded >= o["total_cents"] else "paid", when, reason, order_id))
        if restock:
            for line in db.execute("SELECT product_id,quantity FROM order_items WHERE order_id=?", (order_id,)).fetchall():
                if line["product_id"] is not None:
                    db.execute("UPDATE products SET stock=stock+?,updated_at=? WHERE id=?", (line["quantity"], when, line["product_id"]))
        audit(db, user_id, "refund", "order", order_id, {"amount_cents": amount, "method": method, "reason": reason,
                                                          "restocked": restock, "provider_ref": ref})
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return {"ok": True, "refund_id": cur.lastrowid, "amount_cents": amount, "refunded_cents": total_refunded,
            "fully_refunded": total_refunded >= o["total_cents"], "restocked": restock, "provider_ref": ref}


# ---------------------------------------------------------------- settlement

def _day(value: str | None, business_now) -> str:
    if not value:
        return business_now().date().isoformat()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise OrderingError("Date must be YYYY-MM-DD") from None


def settlement(db, business_now, day: str | None = None) -> dict:
    """Live settlement for one business day. Sales count on the day they were paid, refunds on the day they were made."""
    day = _day(day, business_now)
    sales = db.execute("""SELECT o.id, o.receipt_no, o.total_cents, o.tax_cents, o.payment_method AS method, o.source,
                                 o.paid_at AS at, o.payment_reference AS reference, t.name AS table_name,
                                 COALESCE(c.display_name, '') AS by_name
                          FROM orders o LEFT JOIN dining_tables t ON t.id=o.table_id LEFT JOIN users c ON c.id=o.cashier_id
                          WHERE o.status IN ('paid','refunded') AND substr(o.paid_at,1,10)=? ORDER BY o.paid_at""", (day,)).fetchall()
    refunds = db.execute("""SELECT r.id, r.order_id, o.receipt_no, r.amount_cents, r.method, r.reason, r.created_at AS at,
                                   r.provider_ref AS reference, o.source, t.name AS table_name, COALESCE(u.display_name,'') AS by_name
                            FROM refunds r JOIN orders o ON o.id=r.order_id LEFT JOIN dining_tables t ON t.id=o.table_id
                            LEFT JOIN users u ON u.id=r.created_by WHERE substr(r.created_at,1,10)=? ORDER BY r.created_at""", (day,)).fetchall()
    expenses = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE substr(created_at,1,10)=?", (day,)).fetchone()[0]
    by_method: dict[str, dict] = {}
    for m in METHODS:
        by_method[m] = {"method": m, "label": METHODS[m]["label"], "online": METHODS[m]["online"],
                        "sales_count": 0, "sales_cents": 0, "refund_count": 0, "refund_cents": 0}
    for s in sales:
        row = by_method.setdefault(s["method"] or "cash", {"method": s["method"], "label": s["method"], "online": False,
                                                           "sales_count": 0, "sales_cents": 0, "refund_count": 0, "refund_cents": 0})
        row["sales_count"] += 1
        row["sales_cents"] += s["total_cents"]
    for r in refunds:
        row = by_method.setdefault(r["method"], {"method": r["method"], "label": r["method"], "online": False,
                                                  "sales_count": 0, "sales_cents": 0, "refund_count": 0, "refund_cents": 0})
        row["refund_count"] += 1
        row["refund_cents"] += r["amount_cents"]
    methods = [dict(v, net_cents=v["sales_cents"] - v["refund_cents"]) for v in by_method.values() if v["sales_count"] or v["refund_count"]]
    gross = sum(s["total_cents"] for s in sales)
    refunded = sum(r["amount_cents"] for r in refunds)
    online = [m for m in methods if m["online"]]
    cash = by_method["cash"]
    closing = db.execute("SELECT * FROM day_closings WHERE day=?", (day,)).fetchone()
    transactions = ([{"type": "sale", **dict(s)} for s in sales] + [{"type": "refund", **dict(r)} for r in refunds])
    transactions.sort(key=lambda x: x["at"] or "")
    return {
        "day": day,
        "gross_sales_cents": gross, "sales_count": len(sales),
        "refunds_cents": refunded, "refund_count": len(refunds),
        "net_sales_cents": gross - refunded,
        "tax_cents": sum(s["tax_cents"] for s in sales),
        "expenses_cents": expenses,
        "net_after_expenses_cents": gross - refunded - expenses,
        "online_net_cents": sum(m["net_cents"] for m in online),
        "expected_cash_cents": cash["sales_cents"] - cash["refund_cents"],
        "qr_orders": sum(1 for s in sales if s["source"] == "qr"),
        "test_payments": db.execute("""SELECT COUNT(*) FROM payments WHERE provider='mock' AND status!='pending'
                                       AND substr(updated_at,1,10)=?""", (day,)).fetchone()[0],
        "by_method": methods,
        "transactions": transactions,
        "closing": dict(closing) if closing else None,
        "generated_at": business_now().isoformat(timespec="seconds"),
    }


def close_day(db, business_now, now_iso, audit, user_id: int, body: dict) -> dict:
    report = settlement(db, business_now, body.get("day"))
    try:
        counted = round(float(body.get("counted_cash")) * 100)
    except (TypeError, ValueError):
        raise OrderingError("Enter the cash counted in the drawer") from None
    if counted < 0:
        raise OrderingError("Counted cash cannot be negative")
    snapshot = {k: v for k, v in report.items() if k not in ("transactions", "closing")}
    note = str(body.get("note", ""))[:300]
    db.execute("""INSERT INTO day_closings(day,closed_at,closed_by,counted_cash_cents,expected_cash_cents,note,snapshot) VALUES(?,?,?,?,?,?,?)
                  ON CONFLICT(day) DO UPDATE SET closed_at=excluded.closed_at, closed_by=excluded.closed_by,
                  counted_cash_cents=excluded.counted_cash_cents, expected_cash_cents=excluded.expected_cash_cents,
                  note=excluded.note, snapshot=excluded.snapshot""",
               (report["day"], now_iso(), user_id, counted, report["expected_cash_cents"], note, json.dumps(snapshot, ensure_ascii=False)))
    audit(db, user_id, "close_day", "settlement", report["day"], {"counted_cash_cents": counted,
                                                                  "expected_cash_cents": report["expected_cash_cents"]})
    return {"ok": True, "day": report["day"], "variance_cents": counted - report["expected_cash_cents"]}


def settlement_csv(report: dict) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Kedai POS settlement", report["day"]])
    w.writerow([])
    for label, key in (("Gross sales (RM)", "gross_sales_cents"), ("Refunds (RM)", "refunds_cents"), ("Net sales (RM)", "net_sales_cents"),
                       ("Tax collected (RM)", "tax_cents"), ("Expenses (RM)", "expenses_cents"),
                       ("Net after expenses (RM)", "net_after_expenses_cents"), ("Expected cash in drawer (RM)", "expected_cash_cents")):
        w.writerow([label, f"{report[key] / 100:.2f}"])
    w.writerow([])
    w.writerow(["Method", "Sales", "Sales (RM)", "Refunds", "Refunds (RM)", "Net (RM)"])
    for m in report["by_method"]:
        w.writerow([m["label"], m["sales_count"], f"{m['sales_cents'] / 100:.2f}", m["refund_count"],
                    f"{m['refund_cents'] / 100:.2f}", f"{m['net_cents'] / 100:.2f}"])
    w.writerow([])
    w.writerow(["Time", "Type", "Receipt", "Source", "Table", "Method", "Amount (RM)", "Reference", "By", "Reason"])
    for t in report["transactions"]:
        amount = t["total_cents"] if t["type"] == "sale" else -t["amount_cents"]
        w.writerow([t["at"], t["type"], t.get("receipt_no") or "", t.get("source") or "", t.get("table_name") or "",
                    METHODS.get(t["method"], {}).get("label", t["method"]), f"{amount / 100:.2f}", t.get("reference") or "",
                    t.get("by_name") or "", t.get("reason") or ""])
    return ("﻿" + out.getvalue()).encode("utf-8")  # BOM so Excel opens the Chinese text correctly
