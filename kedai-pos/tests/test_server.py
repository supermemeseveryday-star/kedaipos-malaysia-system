"""End-to-end API tests. Run from the kedai-pos folder: python -m unittest discover -s tests"""
import http.cookiejar
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

TMP = tempfile.TemporaryDirectory()
os.environ["KEDAI_DATA_DIR"] = TMP.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with self.opener.open(req, timeout=10) as res:
                raw = res.read()
                return res.status, (json.loads(raw or b"{}") if "json" in res.headers.get("Content-Type", "") else raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw or b"{}")
            except ValueError:
                return exc.code, raw


def start_server_and_sign_in():
    """Starts a test server and signs in the owner and staff member "ali". Test modules share one database."""
    server.init_db()
    httpd = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    owner, staff = Client(base), Client(base)
    status, _ = owner.call("POST", "/api/setup", {"username": "owner", "display_name": "Boss", "password": "password123"})
    if status == 409:
        status, _ = owner.call("POST", "/api/login", {"username": "owner", "password": "password123"})
    assert status == 200
    status, _ = owner.call("POST", "/api/users", {"username": "ali", "display_name": "Ali", "password": "password123"})
    assert status in (201, 409)
    status, _ = staff.call("POST", "/api/login", {"username": "ali", "password": "password123"})
    assert status == 200
    return httpd, base, owner, staff


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, base, cls.owner, cls.staff = start_server_and_sign_in()
        cls.anon = Client(base)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def add_product(self, stock=5, price=2.5):
        status, body = self.owner.call("POST", "/api/products", {"name": "Teh", "price": price, "stock": stock})
        self.assertEqual(status, 201)
        return body["id"]

    def stock_of(self, pid):
        _, products = self.owner.call("GET", "/api/products")
        return next(p["stock"] for p in products if p["id"] == pid)

    def test_setup_only_once(self):
        status, _ = self.anon.call("POST", "/api/setup", {"username": "other", "password": "password123"})
        self.assertEqual(status, 409)

    def test_requires_login(self):
        self.assertEqual(self.anon.call("GET", "/api/products")[0], 401)

    def test_staff_cannot_use_owner_endpoints(self):
        self.assertEqual(self.staff.call("POST", "/api/products", {"name": "X", "price": 1})[0], 403)
        self.assertEqual(self.staff.call("GET", "/api/expenses")[0], 403)
        self.assertEqual(self.staff.call("GET", "/api/users")[0], 403)
        _, settings = self.staff.call("GET", "/api/settings")
        self.assertNotIn("google_client_id", settings)

    def test_cash_sale_deducts_stock_and_blocks_double_settlement(self):
        pid = self.add_product(stock=5)
        _, order = self.staff.call("POST", "/api/orders", {"items": [{"product_id": pid, "quantity": 2}]})
        status, paid = self.staff.call("POST", f"/api/orders/{order['id']}/pay", {"method": "cash", "cash_received": 10})
        self.assertEqual(status, 200)
        self.assertEqual(paid["change_cents"], 500)
        self.assertEqual(self.stock_of(pid), 3)
        self.assertEqual(self.staff.call("POST", f"/api/orders/{order['id']}/pay", {"method": "qr"})[0], 409)
        self.assertEqual(self.stock_of(pid), 3)

    def test_cash_must_cover_total(self):
        pid = self.add_product()
        _, order = self.staff.call("POST", "/api/orders", {"items": [{"product_id": pid, "quantity": 1}]})
        self.assertEqual(self.staff.call("POST", f"/api/orders/{order['id']}/pay", {"method": "cash", "cash_received": 1})[0], 400)

    def test_split_lines_cannot_oversell(self):
        pid = self.add_product(stock=3)
        items = [{"product_id": pid, "quantity": 2}, {"product_id": pid, "quantity": 2}]
        _, order = self.staff.call("POST", "/api/orders", {"items": items})
        status, body = self.staff.call("POST", f"/api/orders/{order['id']}/pay", {"method": "qr"})
        self.assertEqual(status, 409, body)
        self.assertEqual(self.stock_of(pid), 3)

    def test_refund_restores_stock(self):
        pid = self.add_product(stock=4)
        _, order = self.staff.call("POST", "/api/orders", {"items": [{"product_id": pid, "quantity": 1}]})
        self.staff.call("POST", f"/api/orders/{order['id']}/pay", {"method": "qr"})
        self.assertEqual(self.staff.call("POST", f"/api/orders/{order['id']}/refund", {})[0], 403)
        self.assertEqual(self.owner.call("POST", f"/api/orders/{order['id']}/refund", {"note": "wrong item"})[0], 200)
        self.assertEqual(self.stock_of(pid), 4)

    def test_void_only_open_orders(self):
        pid = self.add_product()
        _, order = self.staff.call("POST", "/api/orders", {"items": [{"product_id": pid, "quantity": 1}]})
        self.assertEqual(self.owner.call("DELETE", f"/api/orders/{order['id']}")[0], 200)
        self.assertEqual(self.owner.call("DELETE", f"/api/orders/{order['id']}")[0], 409)

    def test_bad_ids_return_404(self):
        self.assertEqual(self.owner.call("DELETE", "/api/orders/abc")[0], 404)
        self.assertEqual(self.owner.call("PUT", "/api/products/abc", {"name": "x"})[0], 404)
        self.assertEqual(self.owner.call("POST", "/api/orders/abc/pay", {"method": "cash"})[0], 404)

    def test_duplicate_username_is_friendly(self):
        status, body = self.owner.call("POST", "/api/users", {"username": "ali", "display_name": "Ali 2", "password": "password123"})
        self.assertEqual(status, 409)
        self.assertNotIn("UNIQUE", body["error"])

    def test_login_locks_after_repeated_failures(self):
        self.owner.call("POST", "/api/users", {"username": "kasim", "display_name": "Kasim", "password": "password123"})
        client = Client(self.owner.base)
        try:
            for _ in range(server.LOGIN_MAX_PER_ACCOUNT):
                self.assertEqual(client.call("POST", "/api/login", {"username": "kasim", "password": "wrong-pass"})[0], 401)
            status, body = client.call("POST", "/api/login", {"username": "kasim", "password": "password123"})
            self.assertEqual(status, 429)
            self.assertGreater(body["retry_after"], 0)
            # Another account on the same device is not locked out.
            self.assertEqual(client.call("POST", "/api/login", {"username": "ali", "password": "password123"})[0], 200)
        finally:
            server.LOGIN_FAILURES.clear()

    def test_successful_login_resets_failures(self):
        client = Client(self.owner.base)
        try:
            for _ in range(server.LOGIN_MAX_PER_ACCOUNT - 1):
                client.call("POST", "/api/login", {"username": "ali", "password": "wrong-pass"})
            self.assertEqual(client.call("POST", "/api/login", {"username": "ali", "password": "password123"})[0], 200)
            self.assertEqual(client.call("POST", "/api/login", {"username": "ali", "password": "wrong-pass"})[0], 401)
            self.assertEqual(client.call("POST", "/api/login", {"username": "ali", "password": "password123"})[0], 200)
        finally:
            server.LOGIN_FAILURES.clear()

    def test_tax_applied_to_new_orders(self):
        self.owner.call("POST", "/api/settings", {"tax_enabled": True, "tax_rate": 6})
        try:
            pid = self.add_product(price=10)
            _, order = self.staff.call("POST", "/api/orders", {"items": [{"product_id": pid, "quantity": 1}]})
            _, orders = self.owner.call("GET", "/api/orders")
            saved = next(o for o in orders if o["id"] == order["id"])
            self.assertEqual((saved["subtotal_cents"], saved["tax_cents"], saved["total_cents"]), (1000, 60, 1060))
        finally:
            self.owner.call("POST", "/api/settings", {"tax_enabled": False})


if __name__ == "__main__":
    unittest.main()
