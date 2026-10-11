#!/usr/bin/env python3
"""Kedai POS: a small, local-first shop POS server using only Python's stdlib."""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import io
import json
import math
import mimetypes
import os
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
import zipfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import ordering

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA = Path(os.environ.get("KEDAI_DATA_DIR", ROOT / "data"))
IMAGES = DATA / "images"
DB_PATH = DATA / "kedai.sqlite3"
HOST = os.environ.get("KEDAI_HOST", "0.0.0.0")
PORT = int(os.environ.get("KEDAI_PORT", "8765"))
MAX_BODY = 10 * 1024 * 1024
DB_LOCK = threading.RLock()
SESSIONS: dict[str, tuple[int, float]] = {}
LOGIN_FAILURES: dict[str, list[float]] = {}
LOGIN_WINDOW = 15 * 60
LOGIN_MAX_PER_ACCOUNT = 5
LOGIN_MAX_PER_DEVICE = 20
OAUTH_STATES: dict[str, tuple[int, float, str]] = {}
CHECKOUT_HITS: dict[str, list[float]] = {}
CHECKOUT_WINDOW = 10 * 60
CHECKOUT_MAX_PER_DEVICE = 30
# Paths a customer may reach from the internet (through the tunnel). Everything else is shop-only.
PUBLIC_PATHS = ("/order", "/order.html", "/order.js", "/order.css", "/pay/mock", "/mockpay.html", "/favicon.ico")
PUBLIC_PREFIXES = ("/api/public/", "/api/payments/webhook/", "/uploads/")
GOOGLE_TOKEN_CACHE: tuple[str, float] | None = None
GOOGLE_SCOPES = "https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/userinfo.email"

DATA.mkdir(parents=True, exist_ok=True)
IMAGES.mkdir(parents=True, exist_ok=True)


def business_zone():
    name = os.environ.get("KEDAI_TIMEZONE", "Asia/Kuala_Lumpur")
    if name in ("Asia/Kuala_Lumpur", "MYT"):
        # Windows Python installations often lack the IANA database. Malaysia
        # uses UTC+08:00 year-round, so this fixed offset keeps the default self-contained.
        return timezone(timedelta(hours=8), "MYT")
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=8), "MYT")


def now_iso() -> str:
    return datetime.now(business_zone()).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db() -> None:
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner','staff')),
            password_hash TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            sku TEXT NOT NULL DEFAULT '',
            price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
            stock REAL NOT NULL DEFAULT 0,
            image TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT UNIQUE,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','paid','void','refunded')),
            created_by INTEGER NOT NULL REFERENCES users(id),
            cashier_id INTEGER REFERENCES users(id),
            subtotal_cents INTEGER NOT NULL,
            tax_cents INTEGER NOT NULL DEFAULT 0,
            total_cents INTEGER NOT NULL,
            payment_method TEXT,
            payment_reference TEXT NOT NULL DEFAULT '',
            cash_received_cents INTEGER NOT NULL DEFAULT 0,
            change_cents INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            paid_at TEXT,
            refunded_at TEXT,
            refund_note TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            product_name TEXT NOT NULL,
            sku TEXT NOT NULL DEFAULT '',
            quantity REAL NOT NULL,
            unit_price_cents INTEGER NOT NULL,
            line_total_cents INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
            paid_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL DEFAULT '',
            details TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
        """)
        ordering.migrate(db, now_iso, pass_hash)
        ordering.ensure_secrets(db, setting, set_setting)


def business_now() -> datetime:
    return datetime.now(business_zone())


def as_dict(row):
    return dict(row) if row is not None else None


def audit(db, user_id, action, kind, entity_id="", details=None):
    db.execute("INSERT INTO audit_log(user_id,action,entity_type,entity_id,details,created_at) VALUES(?,?,?,?,?,?)",
               (user_id, action, kind, str(entity_id), json.dumps(details or {}, ensure_ascii=False), now_iso()))


def pass_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return base64.urlsafe_b64encode(salt + value).decode()


def check_password(password: str, packed: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(packed.encode())
        return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac("sha256", password.encode(), raw[:16], 310_000))
    except Exception:
        return False


def money(cents: int) -> str:
    return f"{cents / 100:.2f}"


def finite_number(value, label: str, minimum: float = 0, maximum: float = 1_000_000_000) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
    return number


class NotFound(Exception):
    """Raised for API paths that do not name a valid record; answered with 404."""


def path_id(path: str, index: int) -> int:
    """Return the numeric id segment of an API path, or raise NotFound."""
    try:
        return int(path.split("/")[index])
    except (IndexError, ValueError):
        raise NotFound() from None


def login_keys(ip: str, username: str) -> tuple[str, str]:
    return f"{ip}|{username}", ip


def login_retry_after(ip: str, username: str) -> int:
    """Seconds until this device may try this account again; 0 when allowed."""
    now = time.time()
    wait = 0
    for key, limit in zip(login_keys(ip, username), (LOGIN_MAX_PER_ACCOUNT, LOGIN_MAX_PER_DEVICE)):
        recent = [t for t in LOGIN_FAILURES.get(key, []) if t > now - LOGIN_WINDOW]
        if recent:
            LOGIN_FAILURES[key] = recent
        else:
            LOGIN_FAILURES.pop(key, None)
        if len(recent) >= limit:
            wait = max(wait, math.ceil(recent[-limit] + LOGIN_WINDOW - now))
    return wait


def record_login_failure(ip: str, username: str) -> None:
    for key in login_keys(ip, username):
        LOGIN_FAILURES.setdefault(key, []).append(time.time())


def http_json(url, method="GET", payload=None, headers=None, form=False):
    data = None
    h = dict(headers or {})
    if payload is not None:
        if form:
            data = urllib.parse.urlencode(payload).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(payload).encode()
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1200]
        raise RuntimeError(f"Google API ({exc.code}): {detail}") from exc


def setting(db, key, default=None):
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_setting(db, key, value):
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, json.dumps(value, ensure_ascii=False)))


def google_access_token(db):
    global GOOGLE_TOKEN_CACHE
    if GOOGLE_TOKEN_CACHE and GOOGLE_TOKEN_CACHE[1] > time.time():
        return GOOGLE_TOKEN_CACHE[0]
    client_id=setting(db,"google_client_id","")
    client_secret=setting(db,"google_client_secret","")
    refresh=setting(db,"google_refresh_token","")
    if not client_id or not client_secret or not refresh:
        raise RuntimeError("Connect the owner's Google account first")
    result=http_json("https://oauth2.googleapis.com/token", "POST", {
        "client_id":client_id,"client_secret":client_secret,"refresh_token":refresh,"grant_type":"refresh_token"
    }, form=True)
    token=result["access_token"]
    GOOGLE_TOKEN_CACHE=(token,time.time()+max(60,int(result.get("expires_in",3600))-120))
    return token


def sheets_call(db, method, path, payload=None, query=None):
    token=google_access_token(db)
    url="https://sheets.googleapis.com/v4/"+path
    if query:
        url+="?"+urllib.parse.urlencode(query)
    return http_json(url, method, payload, {"Authorization":"Bearer "+token})


def sync_google_sheet():
    """POS-first sheet sync. Sales are exports; owner-enabled product/expense edits import."""
    with DB_LOCK, connect() as db:
        sheet_id=setting(db,"google_sheet_id","")
        enabled=setting(db,"sheet_sync_enabled",False)
        if not enabled:
            raise RuntimeError("Enable Google Sheets sync in Settings first")
        if not sheet_id:
            created=sheets_call(db,"POST","spreadsheets",{"properties":{"title":setting(db,"shop_name","Kedai POS")+" POS"},"sheets":[{"properties":{"title":"Products"}},{"properties":{"title":"Sales"}},{"properties":{"title":"Expenses"}}]})
            sheet_id=created["spreadsheetId"]
            set_setting(db,"google_sheet_id",sheet_id)
            set_setting(db,"google_sheet_url",created.get("spreadsheetUrl",""))
        meta=sheets_call(db,"GET",f"spreadsheets/{urllib.parse.quote(sheet_id,safe='')}",query={"fields":"sheets.properties.title"})
        titles={x["properties"]["title"] for x in meta.get("sheets",[])}
        missing=[name for name in ("Products","Sales","Expenses") if name not in titles]
        if missing:
            sheets_call(db,"POST",f"spreadsheets/{urllib.parse.quote(sheet_id,safe='')}:batchUpdate",{"requests":[{"addSheet":{"properties":{"title":name}}} for name in missing]})
        headers={"Products":["KedaiId","Name","Category","SKU","PriceRM","Stock","Active","UpdatedAt"],
                 "Sales":["KedaiId","Receipt","Status","SubtotalRM","TaxRM","TotalRM","PaymentMethod","CreatedAt","PaidAt","Cashier","CashReceivedRM","ChangeRM","RefundedAt","RefundNote"],
                 "Expenses":["KedaiId","Description","Category","AmountRM","CreatedAt"]}
        def values(tab, rng):
            res=sheets_call(db,"GET",f"spreadsheets/{urllib.parse.quote(sheet_id,safe='')}/values/{urllib.parse.quote(tab+'!'+rng,safe='')}",query={"valueRenderOption":"UNFORMATTED_VALUE"})
            return res.get("values",[])
        def write_table(tab, rows):
            quoted=urllib.parse.quote(tab+"!A1:Z10000",safe="")
            sheets_call(db,"POST",f"spreadsheets/{urllib.parse.quote(sheet_id,safe='')}/values/{quoted}:clear",{})
            if rows:
                end_col=chr(64+len(rows[0]))
                end_row=max(1,len(rows))
                rng=urllib.parse.quote(f"{tab}!A1:{end_col}{end_row}",safe="")
                sheets_call(db,"PUT",f"spreadsheets/{urllib.parse.quote(sheet_id,safe='')}/values/{rng}",{"majorDimension":"ROWS","values":rows},query={"valueInputOption":"RAW"})
        for tab, head in headers.items():
            existing=values(tab,"A1:"+chr(64+len(head))+"1")
            if not existing:
                rng=urllib.parse.quote(f"{tab}!A1:{chr(64+len(head))}1",safe="")
                sheets_call(db,"PUT",f"spreadsheets/{urllib.parse.quote(sheet_id,safe='')}/values/{rng}",{"values":[head]},query={"valueInputOption":"RAW"})
        product_rows=values("Products","A1:H2000")
        prod_base=setting(db,"sheet_products_baseline",{})
        if setting(db,"sheets_import_products",False) and len(product_rows)>1:
            for row in product_rows[1:]:
                if len(row)<6:
                    continue
                try:
                    pid=int(row[0]) if row[0] else 0
                    name=str(row[1]).strip(); category=str(row[2] or "General"); sku=str(row[3] or "")
                    price=round(finite_number(row[4], "Price")*100); stock=finite_number(row[5], "Stock")
                    if not name or price<0 or stock<0:
                        continue
                except (ValueError,TypeError):
                    continue
                if not pid:
                    cur=db.execute("INSERT INTO products(name,category,sku,price_cents,stock,updated_at) VALUES(?,?,?,?,?,?)",(name,category,sku,price,stock,now_iso()))
                    audit(db,None,"import_sheet","product",cur.lastrowid,{"source":"Google Sheets"})
                    continue
                local=db.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
                if not local:
                    continue
                fields={"name":name,"category":category,"sku":sku,"price_cents":price,"stock":stock}
                base=prod_base.get(str(pid))
                if base and fields!={k:base.get(k) for k in fields}:
                    current={"name":local["name"],"category":local["category"],"sku":local["sku"],"price_cents":local["price_cents"],"stock":local["stock"]}
                    if current=={k:base.get(k) for k in fields}:
                        db.execute("UPDATE products SET name=?,category=?,sku=?,price_cents=?,stock=?,updated_at=? WHERE id=?",(name,category,sku,price,stock,now_iso(),pid))
                        audit(db,None,"import_sheet","product",pid,{"source":"Google Sheets"})
                    elif current!=fields:
                        audit(db,None,"sync_conflict","product",pid,{"winner":"POS"})
        products=db.execute("SELECT * FROM products ORDER BY id").fetchall()
        product_table=[headers["Products"]]
        baseline={}
        for p in products:
            product_table.append([p["id"],p["name"],p["category"],p["sku"],money(p["price_cents"]),p["stock"],p["active"],p["updated_at"]])
            baseline[str(p["id"]) ]={"name":p["name"],"category":p["category"],"sku":p["sku"],"price_cents":p["price_cents"],"stock":p["stock"]}
        write_table("Products",product_table)
        set_setting(db,"sheet_products_baseline",baseline)
        expense_rows=values("Expenses","A1:E2000")
        exp_base=setting(db,"sheet_expenses_baseline",{})
        if setting(db,"sheets_import_expenses",False) and len(expense_rows)>1:
            for row in expense_rows[1:]:
                if len(row)<4:continue
                try:
                    eid=int(row[0]) if row[0] else 0; desc=str(row[1]).strip(); category=str(row[2] or "General"); amount=round(finite_number(row[3], "Amount", 0.01)*100)
                    if not desc or amount<=0:continue
                except (ValueError,TypeError):continue
                if not eid:
                    cur=db.execute("INSERT INTO expenses(description,category,amount_cents,created_at) VALUES(?,?,?,?)",(desc,category,amount,now_iso()))
                    audit(db,None,"import_sheet","expense",cur.lastrowid,{"source":"Google Sheets"})
                    continue
                local=db.execute("SELECT * FROM expenses WHERE id=?",(eid,)).fetchone(); base=exp_base.get(str(eid))
                fields={"description":desc,"category":category,"amount_cents":amount}
                if local and base and fields!={k:base.get(k) for k in fields}:
                    current={"description":local["description"],"category":local["category"],"amount_cents":local["amount_cents"]}
                    if current=={k:base.get(k) for k in fields}:
                        db.execute("UPDATE expenses SET description=?,category=?,amount_cents=? WHERE id=?",(desc,category,amount,eid))
                        audit(db,None,"import_sheet","expense",eid,{"source":"Google Sheets"})
                    elif current!=fields:
                        audit(db,None,"sync_conflict","expense",eid,{"winner":"POS"})
        expenses=db.execute("SELECT * FROM expenses ORDER BY id").fetchall()
        expense_table=[headers["Expenses"]]; exp_snapshot={}
        for x in expenses:
            expense_table.append([x["id"],x["description"],x["category"],money(x["amount_cents"]),x["created_at"]])
            exp_snapshot[str(x["id"]) ]={"description":x["description"],"category":x["category"],"amount_cents":x["amount_cents"]}
        write_table("Expenses",expense_table);set_setting(db,"sheet_expenses_baseline",exp_snapshot)
        orders=db.execute("SELECT o.*,u.display_name cashier FROM orders o LEFT JOIN users u ON u.id=o.cashier_id ORDER BY o.id").fetchall()
        sales=[headers["Sales"]]
        for o in orders:
            sales.append([o["id"],o["receipt_no"] or "",o["status"],money(o["subtotal_cents"]),money(o["tax_cents"]),money(o["total_cents"]),o["payment_method"] or "",o["created_at"],o["paid_at"] or "",o["cashier"] or "",money(o["cash_received_cents"]),money(o["change_cents"]),o["refunded_at"] or "",o["refund_note"]])
        write_table("Sales",sales)
        set_setting(db,"google_sync_at",now_iso());set_setting(db,"google_sync_error","")
        return {"ok":True,"products":len(products),"expenses":len(expenses),"orders":len(orders),"url":setting(db,"google_sheet_url","")}


def google_sync_loop():
    while True:
        time.sleep(90)
        try:
            with connect() as db:
                ready=setting(db,"sheet_sync_enabled",False) and setting(db,"google_refresh_token","")
            if ready:
                sync_google_sheet()
        except Exception as exc:
            with connect() as db:
                set_setting(db,"google_sync_error",str(exc)[:1000])


class Handler(BaseHTTPRequestHandler):
    server_version = "KedaiPOS/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, data, status=200, headers=None):
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("Request is too large")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def user(self):
        cookie = self.headers.get("Cookie", "")
        token = next((part.strip().split("=", 1)[1] for part in cookie.split(";") if part.strip().startswith("kedai_session=")), None)
        item = SESSIONS.get(token) if token else None
        if not item or item[1] < time.time():
            if token:
                SESSIONS.pop(token, None)
            return None
        with connect() as db:
            row = db.execute("SELECT id,username,display_name,role,active FROM users WHERE id=?", (item[0],)).fetchone()
            return as_dict(row) if row and row["active"] else None

    def peer_is_local(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def is_public_request(self) -> bool:
        """True when the request came in from the internet (Cloudflare Tunnel or another reverse proxy)."""
        if self.headers.get("Cf-Connecting-Ip") or self.headers.get("X-Forwarded-For"):
            return True
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        with connect() as db:
            public = urllib.parse.urlsplit(str(setting(db, "public_base_url", "") or "")).hostname or ""
        return bool(public) and host == public.lower()

    def client_ip(self) -> str:
        forwarded = self.headers.get("Cf-Connecting-Ip")
        if forwarded and self.peer_is_local():
            return forwarded.strip()[:64]
        return self.client_address[0]

    def public_blocked(self, path: str) -> bool:
        """Internet visitors may only reach the customer ordering pages; the POS itself stays on the shop network."""
        if not self.is_public_request():
            return False
        return not (path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES))

    def send_bytes(self, raw: bytes, content_type: str, headers=None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def checkout_allowed(self) -> bool:
        ip, now = self.client_ip(), time.time()
        recent = [t for t in CHECKOUT_HITS.get(ip, []) if t > now - CHECKOUT_WINDOW]
        if len(recent) >= CHECKOUT_MAX_PER_DEVICE:
            CHECKOUT_HITS[ip] = recent
            return False
        CHECKOUT_HITS[ip] = recent + [now]
        return True

    def public_get(self, path, query):
        """Customer endpoints: no login."""
        arg = lambda k: (query.get(k) or [""])[0]
        with connect() as db:
            if path == "/api/public/menu":
                return self.send_json(ordering.public_menu(db, setting, arg("table")))
            if path.startswith("/api/public/checkout/"):
                return self.send_json(ordering.checkout_status(db, path.rsplit("/", 1)[1]))
            if path == "/api/public/mock-payment":
                return self.send_json(ordering.mock_payment_page(db, arg("ref")))
        return self.send_json({"error": "Not found"}, 404)

    def public_post(self, path, raw: bytes):
        with DB_LOCK, connect() as db:
            if path == "/api/payments/webhook/mock":
                return self.send_json(ordering.handle_webhook(db, setting, now_iso, audit, business_now, self.headers, raw))
            body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            if not isinstance(body, dict):
                raise ValueError("Invalid request")
            if path == "/api/public/checkout":
                if not self.checkout_allowed():
                    return self.send_json({"error": "Too many orders from this device. Please wait a few minutes."}, 429)
                return self.send_json(ordering.create_checkout(db, setting, now_iso, body, self.client_ip()), 201)
            if path == "/api/public/mock-payment":
                return self.send_json(ordering.mock_complete(db, setting, now_iso, audit, business_now, body))
        return self.send_json({"error": "Not found"}, 404)

    def require_user(self, owner=False):
        user = self.user()
        if not user:
            self.send_json({"error": "Please sign in"}, 401)
            return None
        if owner and user["role"] != "owner":
            self.send_json({"error": "Owner access required"}, 403)
            return None
        return user

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if self.public_blocked(path):
            return self.send_error(404)
        if path.startswith("/api/public/"):
            try:
                return self.public_get(path, urllib.parse.parse_qs(parsed.query))
            except ordering.OrderingError as exc:
                return self.send_json({"error": str(exc)}, exc.status)
        if path.startswith("/api/"):
            self.query = urllib.parse.parse_qs(parsed.query)
            if path == "/api/google/connect":
                return self.google_connect()
            if path == "/api/google/callback":
                return self.google_callback(urllib.parse.parse_qs(parsed.query))
            return self.api_get(path)
        self.serve_static(path)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if self.public_blocked(path):
            return self.send_error(404)
        if path.startswith(("/api/public/", "/api/payments/webhook/")):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 64 * 1024:
                    return self.send_json({"error": "Request is too large"}, 413)
                return self.public_post(path, self.rfile.read(length) if length else b"")
            except ordering.OrderingError as exc:
                return self.send_json({"error": str(exc)}, exc.status)
            except (ValueError, json.JSONDecodeError) as exc:
                return self.send_json({"error": str(exc) or "Invalid request"}, 400)
        if path.startswith("/api/"):
            try:
                body = self.read_json()
                return self.api_post(path, body)
            except NotFound:
                return self.send_json({"error": "Not found"}, 404)
            except ordering.OrderingError as exc:
                return self.send_json({"error": str(exc)}, exc.status)
            except sqlite3.IntegrityError as exc:
                if "users.username" in str(exc):
                    return self.send_json({"error": "That username is already taken"}, 409)
                return self.send_json({"error": "Request conflicts with existing data"}, 409)
            except (ValueError, json.JSONDecodeError) as exc:
                return self.send_json({"error": str(exc) or "Invalid request"}, 400)
            except Exception as exc:
                print("POST error:", repr(exc), file=sys.stderr)
                return self.send_json({"error": str(exc)}, 400)
        self.send_error(404)

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        if self.public_blocked(path):
            return self.send_error(404)
        try:
            body = self.read_json()
            return self.api_put(path, body)
        except NotFound:
            return self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 400)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if self.public_blocked(path):
            return self.send_error(404)
        try:
            return self.api_delete(path)
        except NotFound:
            return self.send_json({"error": "Not found"}, 404)

    def serve_static(self, path):
        if path.startswith("/uploads/"):
            name = path.rsplit("/", 1)[-1]
            if not name or name != Path(name).name:
                return self.send_error(404)
            candidate = IMAGES / name
            if not candidate.is_file():
                return self.send_error(404)
            content = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "private, max-age=86400")
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/":
            path = "/index.html"
        elif path == "/order":
            path = "/order.html"
        elif path == "/pay/mock":
            path = "/mockpay.html"
        candidate = (STATIC / path.lstrip("/")).resolve()
        if STATIC.resolve() not in candidate.parents and candidate != STATIC.resolve():
            return self.send_error(403)
        if not candidate.is_file():
            return self.send_error(404)
        content = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def api_get(self, path):
        with connect() as db:
            if path == "/api/status":
                count = db.execute("SELECT count(*) FROM users WHERE username!=?", (ordering.QR_USERNAME,)).fetchone()[0]
                return self.send_json({"setup_required": count == 0, "user": self.user(), "time": now_iso()})
            if path == "/api/session":
                return self.send_json({"user": self.user()})
            user = self.require_user()
            if not user:
                return
            if path == "/api/products":
                rows = db.execute("SELECT * FROM products WHERE active=1 ORDER BY category,name").fetchall()
                return self.send_json([as_dict(r) for r in rows])
            if path == "/api/orders":
                rows = db.execute("SELECT o.*,u.display_name AS created_by_name,c.display_name AS cashier_name,t.name AS table_name FROM orders o JOIN users u ON u.id=o.created_by LEFT JOIN users c ON c.id=o.cashier_id LEFT JOIN dining_tables t ON t.id=o.table_id ORDER BY o.id DESC LIMIT 300").fetchall()
                result = [as_dict(r) for r in rows]
                for row in result:
                    row["items"] = [as_dict(x) for x in db.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (row["id"],)).fetchall()]
                return self.send_json(result)
            if path == "/api/expenses":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                rows = db.execute("SELECT e.*,u.display_name AS paid_by_name FROM expenses e LEFT JOIN users u ON u.id=e.paid_by ORDER BY e.id DESC LIMIT 500").fetchall()
                return self.send_json([as_dict(r) for r in rows])
            if path == "/api/summary":
                open_orders = db.execute("SELECT COUNT(*) FROM orders WHERE status='open'").fetchone()[0]
                day = business_now().date().isoformat()
                if user["role"] != "owner":
                    return self.send_json({"date":day,"open_orders":open_orders})
                # Same figures as the settlement: sales on the day paid, refunds on the day refunded.
                report = ordering.settlement(db, business_now, day)
                return self.send_json({"date": day, "orders": report["sales_count"], "sales_cents": report["gross_sales_cents"],
                                       "refunds_cents": report["refunds_cents"], "expenses_cents": report["expenses_cents"],
                                       "net_cents": report["net_after_expenses_cents"], "open_orders": open_orders,
                                       "by_method": [{"payment_method": m["method"], "n": m["sales_count"], "total": m["net_cents"]} for m in report["by_method"]]})
            if path == "/api/tables":
                if user["role"] != "owner":
                    return self.send_json({"error": "Owner access required"}, 403)
                return self.send_json(ordering.list_tables(db))
            if path in ("/api/settlement", "/api/settlement/export"):
                if user["role"] != "owner":
                    return self.send_json({"error": "Owner access required"}, 403)
                try:
                    report = ordering.settlement(db, business_now, (getattr(self, "query", {}).get("day") or [""])[0])
                except ordering.OrderingError as exc:
                    return self.send_json({"error": str(exc)}, exc.status)
                if path.endswith("/export"):
                    return self.send_bytes(ordering.settlement_csv(report), "text/csv; charset=utf-8",
                                           {"Content-Disposition": f"attachment; filename=kedai-pos-settlement-{report['day']}.csv"})
                return self.send_json(report)
            if path == "/api/settings":
                values = {r["key"]: json.loads(r["value"]) for r in db.execute("SELECT * FROM settings")}
                values["google_secret_configured"] = bool(values.pop("google_client_secret", ""))
                values.pop("google_refresh_token", None)
                values.pop("mock_gateway_secret", None)
                values["payment_methods"] = [{"id": k, "label": v["label"], "online": v["online"]} for k, v in ordering.METHODS.items()]
                if user["role"] != "owner":
                    values={k:v for k,v in values.items() if k in {"shop_name","shop_address","shop_phone","language","currency","timezone","merchant_qr","tax_enabled","tax_label","tax_rate"}}
                return self.send_json(values)
            if path == "/api/users":
                if user["role"] != "owner":
                    return self.send_json({"error": "Owner access required"}, 403)
                return self.send_json([as_dict(r) for r in db.execute("SELECT id,username,display_name,role,active,created_at FROM users WHERE username!=? ORDER BY id", (ordering.QR_USERNAME,))])
            if path == "/api/audit":
                if user["role"] != "owner":
                    return self.send_json({"error": "Owner access required"}, 403)
                return self.send_json([as_dict(r) for r in db.execute("SELECT a.*,u.display_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 200")])
            if path == "/api/export":
                if user["role"] != "owner":
                    return self.send_json({"error": "Owner access required"}, 403)
                tables = {}
                for table in ("products", "orders", "order_items", "expenses", "users", "audit_log"):
                    if table == "users":
                        tables[table] = [as_dict(r) for r in db.execute("SELECT id,username,display_name,role,active,created_at FROM users")]
                    else:
                        tables[table] = [as_dict(r) for r in db.execute(f"SELECT * FROM {table}")]
                return self.send_json({"exported_at": now_iso(), "data": tables})
            if path == "/api/backup":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                source=connect()
                backup_path=DATA/".backup-tmp.sqlite3"
                target=sqlite3.connect(backup_path)
                source.backup(target)
                target.close();source.close()
                package=io.BytesIO()
                with zipfile.ZipFile(package,"w",zipfile.ZIP_DEFLATED) as archive:
                    archive.write(backup_path,"kedai.sqlite3")
                    for image in IMAGES.iterdir():
                        if image.is_file():archive.write(image,"images/"+image.name)
                try:backup_path.unlink()
                except OSError:pass
                raw=package.getvalue()
                self.send_response(200);self.send_header("Content-Type","application/zip")
                self.send_header("Content-Disposition",f"attachment; filename=kedai-pos-backup-{datetime.now(business_zone()).strftime('%Y%m%d')}.zip")
                self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(raw)
                return
        return self.send_json({"error": "Not found"}, 404)

    def api_post(self, path, body):
        global GOOGLE_TOKEN_CACHE
        with DB_LOCK, connect() as db:
            if path == "/api/setup":
                if db.execute("SELECT count(*) FROM users WHERE username!=?", (ordering.QR_USERNAME,)).fetchone()[0]:
                    return self.send_json({"error": "Setup has already been completed"}, 409)
                username = str(body.get("username", "owner")).strip().lower()
                display = str(body.get("display_name", "Owner")).strip() or "Owner"
                password = str(body.get("password", ""))
                if len(username) < 3 or len(password) < 8:
                    return self.send_json({"error": "Username must have 3+ characters and password 8+ characters"}, 400)
                cur = db.execute("INSERT INTO users(username,display_name,role,password_hash,created_at) VALUES(?,?,'owner',?,?)",
                                 (username, display, pass_hash(password), now_iso()))
                audit(db, cur.lastrowid, "setup", "user", cur.lastrowid)
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = (cur.lastrowid, time.time()+60*60*24*14)
                return self.send_json({"user": {"id": cur.lastrowid,"username": username,"display_name": display,"role":"owner"}},
                                      headers={"Set-Cookie": f"kedai_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=1209600"})
            if path == "/api/login":
                username = str(body.get("username", "")).strip().lower()
                ip = self.client_address[0]
                wait = login_retry_after(ip, username)
                if wait:
                    minutes = max(1, math.ceil(wait / 60))
                    return self.send_json({"error": f"Too many failed sign-in attempts. Try again in {minutes} min.", "retry_after": wait},
                                          429, {"Retry-After": str(wait)})
                row = db.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
                if not row or not check_password(str(body.get("password", "")), row["password_hash"]):
                    record_login_failure(ip, username)
                    audit(db, None, "login_failed", "user", username, {"ip": ip})
                    return self.send_json({"error": "Incorrect username or password"}, 401)
                LOGIN_FAILURES.pop(login_keys(ip, username)[0], None)
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = (row["id"], time.time()+60*60*24*14)
                return self.send_json({"user": {"id":row["id"],"username":row["username"],"display_name":row["display_name"],"role":row["role"]}},
                                      headers={"Set-Cookie": f"kedai_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=1209600"})
        user = self.require_user()
        if not user:
            return
        with DB_LOCK, connect() as db:
            if path == "/api/logout":
                cookie = self.headers.get("Cookie", "")
                token = next((p.strip().split("=",1)[1] for p in cookie.split(";") if p.strip().startswith("kedai_session=")), "")
                SESSIONS.pop(token, None)
                return self.send_json({"ok": True}, headers={"Set-Cookie": "kedai_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"})
            if path == "/api/products":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                name = str(body.get("name", "")).strip()
                if not name:
                    return self.send_json({"error": "Product name is required"}, 400)
                price = round(finite_number(body.get("price", 0), "Price")*100)
                stock = finite_number(body.get("stock", 0), "Stock")
                image = self.save_image(body.get("image", ""))
                cur = db.execute("INSERT INTO products(name,category,sku,price_cents,stock,image,updated_at) VALUES(?,?,?,?,?,?,?)",
                                 (name, str(body.get("category", "General")).strip() or "General", str(body.get("sku", "")).strip(), price, stock, image, now_iso()))
                audit(db, user["id"], "create", "product", cur.lastrowid, {"name": name})
                return self.send_json({"id": cur.lastrowid}, 201)
            if path == "/api/orders":
                items = body.get("items") or []
                if not items:
                    return self.send_json({"error": "Order has no items"}, 400)
                db.execute("BEGIN IMMEDIATE")
                normalized=[]; subtotal=0
                for item in items:
                    try:
                        pid=int(item.get("product_id", 0)); qty=finite_number(item.get("quantity", 1), "Quantity", 0.000001, 100000)
                    except (TypeError, ValueError, OverflowError) as exc:
                        db.rollback()
                        return self.send_json({"error":str(exc) or "Invalid product or quantity"},400)
                    if qty <= 0:
                        db.rollback()
                        return self.send_json({"error": "Invalid quantity"}, 400)
                    product=db.execute("SELECT * FROM products WHERE id=? AND active=1",(pid,)).fetchone()
                    if not product:
                        db.rollback()
                        return self.send_json({"error": "Product no longer available"},409)
                    line=round(product["price_cents"]*qty)
                    subtotal+=line
                    normalized.append((product,qty,line))
                try:
                    enabled = json.loads(db.execute("SELECT value FROM settings WHERE key='tax_enabled'").fetchone()[0])
                    rate = float(json.loads(db.execute("SELECT value FROM settings WHERE key='tax_rate'").fetchone()[0])) if enabled else 0
                except (TypeError, ValueError, json.JSONDecodeError):
                    rate = 0
                tax=round(subtotal*rate/100)
                total=subtotal+tax
                cur=db.execute("INSERT INTO orders(created_by,subtotal_cents,tax_cents,total_cents,created_at,note) VALUES(?,?,?,?,?,?)",
                               (user["id"],subtotal,tax,total,now_iso(),str(body.get("note",""))[:500]))
                oid=cur.lastrowid
                for product,qty,line in normalized:
                    db.execute("INSERT INTO order_items(order_id,product_id,product_name,sku,quantity,unit_price_cents,line_total_cents) VALUES(?,?,?,?,?,?,?)",
                               (oid,product["id"],product["name"],product["sku"],qty,product["price_cents"],line))
                audit(db,user["id"],"create","order",oid,{"total_cents":subtotal})
                db.commit()
                return self.send_json({"id":oid,"status":"open"},201)
            if path == "/api/expenses":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                desc=str(body.get("description","")).strip()
                amount=round(finite_number(body.get("amount",0), "Amount", 0.01)*100)
                if not desc or amount <= 0:
                    return self.send_json({"error":"Description and positive amount are required"},400)
                cur=db.execute("INSERT INTO expenses(description,category,amount_cents,paid_by,created_at) VALUES(?,?,?,?,?)",
                               (desc,str(body.get("category","General")),amount,user["id"],now_iso()))
                audit(db,user["id"],"create","expense",cur.lastrowid,{"amount_cents":amount})
                return self.send_json({"id":cur.lastrowid},201)
            if path == "/api/users":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                username=str(body.get("username","")).strip().lower(); display=str(body.get("display_name","")).strip(); password=str(body.get("password",""))
                if len(username)<3 or len(password)<8 or not display:
                    return self.send_json({"error":"Name, 3+ character username, and 8+ character password are required"},400)
                cur=db.execute("INSERT INTO users(username,display_name,role,password_hash,created_at) VALUES(?,?,'staff',?,?)",
                               (username,display,pass_hash(password),now_iso()))
                audit(db,user["id"],"create","staff",cur.lastrowid,{"username":username})
                return self.send_json({"id":cur.lastrowid},201)
            if path == "/api/settings":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                allowed={"shop_name","shop_address","shop_phone","language","currency","timezone","merchant_qr","tax_enabled","tax_label","tax_rate","google_client_id","google_client_secret","google_sheet_id","sheet_sync_enabled","sheets_import_products","sheets_import_expenses","qr_ordering_enabled","qr_payment_methods","public_base_url"}
                for key,val in body.items():
                    if key in allowed:
                        if key == "qr_ordering_enabled":
                            val = bool(val)
                        if key == "qr_payment_methods":
                            if not isinstance(val, list) or not all(m in ordering.ONLINE_METHODS for m in val):
                                return self.send_json({"error":"Unknown payment method"},400)
                        if key == "public_base_url":
                            val = str(val).strip().rstrip("/")
                            if val and urllib.parse.urlsplit(val).scheme != "https":
                                return self.send_json({"error":"The public address must start with https://"},400)
                        if key == "tax_rate":
                            val = finite_number(val, "Tax rate", 0, 100)
                        if key == "language" and val not in ("zh", "en", "ms"):
                            return self.send_json({"error":"Choose Chinese, English, or Malay"},400)
                        if key == "google_client_secret" and not str(val).strip():
                            continue
                        if key=="merchant_qr":
                            val=self.save_image(val)
                        db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,json.dumps(val,ensure_ascii=False)))
                if "google_client_id" in body or ("google_client_secret" in body and str(body.get("google_client_secret","")).strip()):
                    GOOGLE_TOKEN_CACHE=None
                audit(db,user["id"],"update","settings","shop",{k:v for k,v in body.items() if k not in ("google_client_secret","merchant_qr")})
                return self.send_json({"ok":True})
            if path == "/api/google/sync":
                if user["role"]!="owner":
                    return self.send_json({"error":"Owner access required"},403)
                try:
                    result=sync_google_sheet()
                    return self.send_json(result)
                except Exception as exc:
                    set_setting(db,"google_sync_error",str(exc)[:1000])
                    return self.send_json({"error":str(exc)},502)
            if path.startswith("/api/orders/") and path.endswith("/pay"):
                if user["role"] not in ("owner","staff"):
                    return self.send_json({"error":"Access denied"},403)
                oid=path_id(path,3); method=str(body.get("method",""))
                if method not in ("cash","qr"):
                    return self.send_json({"error":"Choose cash or DuitNow QR"},400)
                db.execute("BEGIN IMMEDIATE")
                order=db.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
                if not order:
                    db.rollback(); return self.send_json({"error":"Order not found"},404)
                if order["status"]!="open":
                    db.rollback(); return self.send_json({"error":"This order is already settled or closed"},409)
                lines=db.execute("SELECT * FROM order_items WHERE order_id=?",(oid,)).fetchall()
                # Sum per product so an item split across several lines cannot oversell.
                needed={}
                for line in lines:
                    if line["product_id"] is not None:
                        qty,name=needed.get(line["product_id"],(0,line["product_name"]))
                        needed[line["product_id"]]=(qty+line["quantity"],name)
                for pid,(qty,name) in needed.items():
                    product=db.execute("SELECT stock FROM products WHERE id=?",(pid,)).fetchone()
                    if product and product["stock"] < qty:
                        db.rollback(); return self.send_json({"error":f"Not enough stock for {name}"},409)
                receipt=f"KED-{datetime.now(business_zone()).strftime('%y%m%d')}-{oid:05d}"
                paid=now_iso()
                try:
                    received = round(finite_number(body.get("cash_received", order["total_cents"]/100), "Cash received")*100) if method == "cash" else 0
                except ValueError as exc:
                    db.rollback();return self.send_json({"error":str(exc)},400)
                if method == "cash" and received < order["total_cents"]:
                    db.rollback(); return self.send_json({"error":"Cash received must cover the total"},400)
                change = received-order["total_cents"] if method == "cash" else 0
                db.execute("UPDATE orders SET status='paid',receipt_no=?,cashier_id=?,payment_method=?,payment_reference=?,cash_received_cents=?,change_cents=?,paid_at=? WHERE id=? AND status='open'",
                           (receipt,user["id"],method,str(body.get("reference",""))[:100],received,change,paid,oid))
                for line in lines:
                    if line["product_id"] is not None:
                        db.execute("UPDATE products SET stock=stock-?,updated_at=? WHERE id=?",(line["quantity"],paid,line["product_id"]))
                audit(db,user["id"],"settle","order",oid,{"receipt":receipt,"method":method})
                db.commit()
                return self.send_json({"ok":True,"receipt_no":receipt,"paid_at":paid,"change_cents":change})
            if path.startswith("/api/orders/") and path.endswith("/refund"):
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                return self.send_json(ordering.refund_order(db, setting, now_iso, audit, path_id(path,3), user["id"], body))
            if path == "/api/tables":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                table = ordering.create_table(db, str(body.get("name","")), now_iso)
                audit(db,user["id"],"create","table",table["id"],{"name":table["name"]})
                return self.send_json(table, 201)
            if path == "/api/settlement/close":
                if user["role"] != "owner":
                    return self.send_json({"error":"Owner access required"},403)
                return self.send_json(ordering.close_day(db, business_now, now_iso, audit, user["id"], body))
        return self.send_json({"error":"Not found"},404)

    def save_image(self, data):
        if not data:
            return ""
        if not isinstance(data,str) or not data.startswith("data:image/") or "," not in data:
            raise ValueError("Image must be an image upload")
        header, encoded=data.split(",",1)
        ext={"image/png":"png","image/jpeg":"jpg","image/webp":"webp","image/gif":"gif"}.get(header[5:].split(";",1)[0])
        if not ext:
            raise ValueError("Use PNG, JPEG, WebP, or GIF images")
        payload=base64.b64decode(encoded,validate=True)
        if len(payload)>4*1024*1024:
            raise ValueError("Image must be smaller than 4 MB")
        name=secrets.token_hex(16)+"."+ext
        (IMAGES/name).write_bytes(payload)
        return "/uploads/"+name

    def google_connect(self):
        user=self.require_user(owner=True)
        if not user:return
        try:
            from_host = ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            from_host = False
        if not from_host:
            return self.send_json({"error":"Start Google authorization in a browser on the main POS computer"},403)
        host_header=self.headers.get("Host","")
        try:
            host_parts=urllib.parse.urlsplit("//"+host_header)
            hostname=(host_parts.hostname or "").lower()
            host_port=host_parts.port
        except ValueError:
            hostname="";host_port=None
        if hostname not in ("localhost","127.0.0.1") or host_port!=PORT:
            return self.send_json({"error":f"Open the POS on this computer at http://localhost:{PORT} before connecting Google"},400)
        redirect_uri=f"http://{hostname}:{PORT}/api/google/callback"
        with connect() as db:
            client_id=setting(db,"google_client_id","")
            if not client_id:
                return self.send_json({"error":"Enter the Google OAuth client ID in Settings first"},400)
        state=secrets.token_urlsafe(32)
        OAUTH_STATES[state]=(user["id"],time.time()+600,redirect_uri)
        params={"client_id":client_id,"redirect_uri":redirect_uri,"response_type":"code","scope":GOOGLE_SCOPES,
                "access_type":"offline","prompt":"consent","include_granted_scopes":"true","state":state}
        location="https://accounts.google.com/o/oauth2/v2/auth?"+urllib.parse.urlencode(params)
        self.send_response(302);self.send_header("Location",location);self.send_header("Cache-Control","no-store");self.end_headers()

    def google_callback(self, query):
        state=(query.get("state") or [""])[0]
        pending=OAUTH_STATES.pop(state,None)
        if not pending or pending[1]<time.time():
            return self.send_json({"error":"Google authorization expired. Try again from the host computer."},400)
        if (query.get("error") or [None])[0]:
            return self.send_json({"error":"Google authorization was cancelled"},400)
        code=(query.get("code") or [""])[0]
        with connect() as db:
            client_id=setting(db,"google_client_id","");client_secret=setting(db,"google_client_secret","")
            if not client_id or not client_secret:
                return self.send_json({"error":"Google OAuth credentials are missing"},400)
            redirect_uri=pending[2]
            try:
                token=http_json("https://oauth2.googleapis.com/token","POST",{"code":code,"client_id":client_id,"client_secret":client_secret,"redirect_uri":redirect_uri,"grant_type":"authorization_code"},form=True)
                info=http_json("https://www.googleapis.com/oauth2/v2/userinfo",headers={"Authorization":"Bearer "+token["access_token"]})
                if token.get("refresh_token"):
                    set_setting(db,"google_refresh_token",token["refresh_token"])
                set_setting(db,"google_email",info.get("email",""))
                set_setting(db,"google_connected_at",now_iso())
                set_setting(db,"google_sync_error","")
                global GOOGLE_TOKEN_CACHE
                GOOGLE_TOKEN_CACHE=(token["access_token"],time.time()+max(60,int(token.get("expires_in",3600))-120))
            except Exception as exc:
                return self.send_json({"error":str(exc)},502)
        self.send_response(302);self.send_header("Location","/?google=connected");self.send_header("Cache-Control","no-store");self.end_headers()

    def api_put(self,path,body):
        user=self.require_user()
        if not user:return
        with DB_LOCK,connect() as db:
            if path.startswith("/api/products/"):
                if user["role"]!="owner":return self.send_json({"error":"Owner access required"},403)
                pid=path_id(path,3); row=db.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
                if not row:return self.send_json({"error":"Product not found"},404)
                name=str(body.get("name",row["name"])).strip()
                price=round(finite_number(body.get("price",row["price_cents"]/100), "Price")*100)
                stock=finite_number(body.get("stock",row["stock"]), "Stock")
                image=self.save_image(body["image"]) if body.get("image","").startswith("data:image/") else body.get("image",row["image"])
                db.execute("UPDATE products SET name=?,category=?,sku=?,price_cents=?,stock=?,image=?,updated_at=? WHERE id=?",
                           (name,str(body.get("category",row["category"])),str(body.get("sku",row["sku"])),price,stock,image,now_iso(),pid))
                audit(db,user["id"],"update","product",pid,{"name":name})
                return self.send_json({"ok":True})
            if path.startswith("/api/tables/"):
                if user["role"]!="owner":return self.send_json({"error":"Owner access required"},403)
                tid=path_id(path,3)
                if not db.execute("SELECT 1 FROM dining_tables WHERE id=?",(tid,)).fetchone():return self.send_json({"error":"Table not found"},404)
                if "name" in body and str(body["name"]).strip():
                    db.execute("UPDATE dining_tables SET name=? WHERE id=?",(str(body["name"]).strip()[:40],tid))
                if "active" in body:
                    db.execute("UPDATE dining_tables SET active=? WHERE id=?",(1 if body["active"] else 0,tid))
                audit(db,user["id"],"update","table",tid,{k:body[k] for k in ("name","active") if k in body})
                return self.send_json({"ok":True})
            if path.startswith("/api/users/"):
                if user["role"]!="owner":return self.send_json({"error":"Owner access required"},403)
                uid=path_id(path,3)
                if uid==user["id"]:return self.send_json({"error":"Use another owner to disable this account"},400)
                active=1 if body.get("active",True) else 0
                db.execute("UPDATE users SET active=? WHERE id=? AND role='staff' AND username!=?",(active,uid,ordering.QR_USERNAME))
                audit(db,user["id"],"update","staff",uid,{"active":active})
                return self.send_json({"ok":True})
        return self.send_json({"error":"Not found"},404)

    def api_delete(self,path):
        user=self.require_user(owner=True)
        if not user:return
        if path.startswith("/api/products/"):
            pid=path_id(path,3)
            with DB_LOCK,connect() as db:
                db.execute("UPDATE products SET active=0,updated_at=? WHERE id=?",(now_iso(),pid))
                audit(db,user["id"],"archive","product",pid)
            return self.send_json({"ok":True})
        if path.startswith("/api/orders/"):
            oid=path_id(path,3)
            with DB_LOCK,connect() as db:
                row=db.execute("SELECT status FROM orders WHERE id=?",(oid,)).fetchone()
                if not row:return self.send_json({"error":"Order not found"},404)
                if row["status"]!="open":return self.send_json({"error":"Only open orders can be voided here"},409)
                db.execute("UPDATE orders SET status='void' WHERE id=?",(oid,))
                audit(db,user["id"],"void","order",oid)
            return self.send_json({"ok":True})
        return self.send_json({"error":"Not found"},404)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    init_db()
    threading.Thread(target=google_sync_loop, daemon=True, name="google-sheet-sync").start()
    print(f"Kedai POS is running at http://{HOST}:{PORT}")
    print("From other devices, open http://<shop-computer-LAN-IP>:"+str(PORT))
    Server((HOST, PORT), Handler).serve_forever()
