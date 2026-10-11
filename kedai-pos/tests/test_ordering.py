"""Scan-to-order, online payment, refund and settlement tests. Run: python -m unittest discover -s tests"""
import json
import unittest

from test_server import Client, server, start_server_and_sign_in

import ordering

INTERNET = {"Cf-Connecting-Ip": "203.0.113.9"}  # what Cloudflare Tunnel adds to every request from the internet


class OrderingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, base, cls.owner, cls.staff = start_server_and_sign_in()
        cls.guest = Client(base)
        status, _ = cls.owner.call("POST", "/api/settings", {"qr_ordering_enabled": True, "tax_enabled": False})
        assert status == 200
        _, cls.table = cls.owner.call("POST", "/api/tables", {"name": "Table 3"})

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        server.CHECKOUT_HITS.clear()

    # helpers
    def product(self, price=6.5, stock=10, name="Mee Hailam"):
        status, body = self.owner.call("POST", "/api/products", {"name": name, "price": price, "stock": stock})
        self.assertEqual(status, 201)
        return body["id"]

    def stock_of(self, pid):
        _, products = self.owner.call("GET", "/api/products")
        return next(p["stock"] for p in products if p["id"] == pid)

    def checkout(self, items, method="tng", headers=None):
        return self.guest.call("POST", "/api/public/checkout",
                               {"table": self.table["code"], "method": method, "items": items}, headers=headers)

    def pay(self, pay_url, approve=True):
        ref = pay_url.split("ref=", 1)[1]
        return self.guest.call("POST", "/api/public/mock-payment", {"ref": ref, "approve": approve})

    def order_for(self, session):
        _, status = self.guest.call("GET", f"/api/public/checkout/{session}")
        _, orders = self.owner.call("GET", "/api/orders")
        return status, next((o for o in orders if o["receipt_no"] and o["receipt_no"] == status.get("receipt_no")), None)

    def today(self):
        _, report = self.owner.call("GET", "/api/settlement")
        return report

    # customer flow
    def test_menu_needs_no_login_and_hides_inactive_tables(self):
        pid = self.product(name="Kopi Peng")
        status, menu = self.guest.call("GET", f"/api/public/menu?table={self.table['code']}")
        self.assertEqual(status, 200)
        self.assertEqual(menu["table"]["name"], "Table 3")
        self.assertIn(pid, [p["id"] for p in menu["products"]])
        self.assertIn("tng", [m["id"] for m in menu["methods"]])
        self.assertEqual(self.guest.call("GET", "/api/public/menu?table=nope")[0], 404)

    def test_scan_order_pay_reaches_pos_and_deducts_stock(self):
        pid = self.product(price=6.5, stock=10)
        status, co = self.checkout([{"product_id": pid, "quantity": 2, "price": 0.01}])  # client price is ignored
        self.assertEqual(status, 201, co)
        self.assertEqual(co["total_cents"], 1300)
        # Not in the POS until paid
        _, orders = self.owner.call("GET", "/api/orders")
        self.assertFalse(any(o.get("payment_reference") == co["pay_url"].split("ref=")[1] for o in orders))
        self.assertEqual(self.pay(co["pay_url"])[0], 200)
        status, order = self.order_for(co["session"])
        self.assertEqual(status["status"], "paid")
        self.assertEqual((order["source"], order["table_name"], order["payment_method"], order["status"]), ("qr", "Table 3", "tng", "paid"))
        self.assertEqual(self.stock_of(pid), 8)

    def test_declined_payment_creates_no_order(self):
        pid = self.product(stock=5)
        _, co = self.checkout([{"product_id": pid, "quantity": 1}], method="grabpay")
        before = len(self.owner.call("GET", "/api/orders")[1])
        self.pay(co["pay_url"], approve=False)
        self.assertEqual(self.guest.call("GET", f"/api/public/checkout/{co['session']}")[1]["status"], "failed")
        self.assertEqual(len(self.owner.call("GET", "/api/orders")[1]), before)
        self.assertEqual(self.stock_of(pid), 5)

    def test_webhook_rejects_bad_signature_and_ignores_replays(self):
        pid = self.product()
        _, co = self.checkout([{"product_id": pid, "quantity": 1}])
        ref = co["pay_url"].split("ref=")[1]
        raw = json.dumps({"provider_ref": ref, "status": "succeeded", "amount_cents": 650}).encode()
        bad = self.guest.call("POST", "/api/payments/webhook/mock", json.loads(raw), headers={"X-Mock-Signature": "0" * 64})
        self.assertEqual(bad[0], 401)
        with server.connect() as db:
            sig = ordering.gateway(db, server.setting).sign(json.dumps(json.loads(raw)).encode())
        for _ in range(2):  # gateways retry; the second delivery must not create a second order
            status, body = self.guest.call("POST", "/api/payments/webhook/mock", json.loads(raw), headers={"X-Mock-Signature": sig})
            self.assertEqual(status, 200, body)
        self.assertTrue(body.get("duplicate"))
        _, orders = self.owner.call("GET", "/api/orders")
        self.assertEqual(sum(1 for o in orders if o["payment_reference"] == ref), 1)

    def test_sold_out_while_paying_refunds_automatically(self):
        pid = self.product(stock=1)
        _, co = self.checkout([{"product_id": pid, "quantity": 1}])
        self.owner.call("PUT", f"/api/products/{pid}", {"stock": 0})
        self.pay(co["pay_url"])
        status = self.guest.call("GET", f"/api/public/checkout/{co['session']}")[1]
        self.assertEqual(status["status"], "refunded")
        self.assertIsNone(status["receipt_no"])

    def test_scan_to_order_can_be_switched_off(self):
        self.owner.call("POST", "/api/settings", {"qr_ordering_enabled": False})
        try:
            self.assertEqual(self.guest.call("GET", f"/api/public/menu?table={self.table['code']}")[0], 403)
        finally:
            self.owner.call("POST", "/api/settings", {"qr_ordering_enabled": True})

    def test_checkout_rejects_bad_carts(self):
        pid = self.product(stock=2)
        self.assertEqual(self.checkout([{"product_id": pid, "quantity": 3}])[0], 409)
        self.assertEqual(self.checkout([{"product_id": pid, "quantity": 0}])[0], 400)
        self.assertEqual(self.checkout([])[0], 400)
        self.assertEqual(self.checkout([{"product_id": pid, "quantity": 1}], method="bitcoin")[0], 400)

    def test_checkout_rate_limit_per_device(self):
        pid = self.product(stock=100)
        for _ in range(server.CHECKOUT_MAX_PER_DEVICE):
            self.assertEqual(self.checkout([{"product_id": pid, "quantity": 1}], headers=INTERNET)[0], 201)
        self.assertEqual(self.checkout([{"product_id": pid, "quantity": 1}], headers=INTERNET)[0], 429)

    # internet exposure
    def test_internet_visitors_only_reach_customer_pages(self):
        self.assertEqual(self.guest.call("GET", f"/api/public/menu?table={self.table['code']}", headers=INTERNET)[0], 200)
        self.assertEqual(self.guest.call("GET", "/order", headers=INTERNET)[0], 200)
        for method, path in (("GET", "/"), ("GET", "/app.js"), ("GET", "/api/orders"), ("GET", "/api/status"),
                             ("POST", "/api/login"), ("POST", "/api/setup"), ("GET", "/api/backup")):
            self.assertEqual(self.owner.call(method, path, {} if method == "POST" else None, headers=INTERNET)[0], 404, path)

    # refunds and settlement
    def test_partial_then_full_refund_of_cash_sale_updates_settlement(self):
        pid = self.product(price=10, stock=5)
        before = self.today()
        _, order = self.staff.call("POST", "/api/orders", {"items": [{"product_id": pid, "quantity": 1}]})
        self.staff.call("POST", f"/api/orders/{order['id']}/pay", {"method": "cash", "cash_received": 10})
        self.assertEqual(self.staff.call("POST", f"/api/orders/{order['id']}/refund", {"amount": 1})[0], 403)
        status, r = self.owner.call("POST", f"/api/orders/{order['id']}/refund", {"amount": 4, "reason": "cold food"})
        self.assertEqual(status, 200, r)
        self.assertFalse(r["fully_refunded"])
        after = self.today()
        self.assertEqual(after["gross_sales_cents"] - before["gross_sales_cents"], 1000)
        self.assertEqual(after["refunds_cents"] - before["refunds_cents"], 400)
        self.assertEqual(after["expected_cash_cents"] - before["expected_cash_cents"], 600)
        self.assertEqual(self.owner.call("POST", f"/api/orders/{order['id']}/refund", {"amount": 6.01})[0], 400)
        status, r = self.owner.call("POST", f"/api/orders/{order['id']}/refund", {})
        self.assertEqual((status, r["amount_cents"], r["fully_refunded"]), (200, 600, True))
        self.assertEqual(self.stock_of(pid), 4)  # partial refunds do not restock
        self.assertEqual(self.owner.call("POST", f"/api/orders/{order['id']}/refund", {})[0], 409)

    def test_online_refund_goes_through_the_gateway(self):
        pid = self.product(price=8, stock=3)
        _, co = self.checkout([{"product_id": pid, "quantity": 1}], method="applepay")
        self.pay(co["pay_url"])
        _, order = self.order_for(co["session"])
        status, r = self.owner.call("POST", f"/api/orders/{order['id']}/refund", {"reason": "wrong order"})
        self.assertEqual(status, 200, r)
        self.assertTrue(r["provider_ref"].startswith("mockrf_"))
        self.assertTrue(r["restocked"])
        self.assertEqual(self.stock_of(pid), 3)
        methods = {m["method"]: m for m in self.today()["by_method"]}
        self.assertGreaterEqual(methods["applepay"]["refund_cents"], 800)
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT status FROM payments WHERE order_id=?", (order["id"],)).fetchone()[0], "refunded")

    def test_settlement_lists_transactions_exports_csv_and_closes_day(self):
        pid = self.product(price=5, stock=5)
        _, co = self.checkout([{"product_id": pid, "quantity": 1}], method="boost")
        self.pay(co["pay_url"])
        report = self.today()
        self.assertIn("boost", [m["method"] for m in report["by_method"]])
        self.assertTrue(any(t["type"] == "sale" and t["method"] == "boost" for t in report["transactions"]))
        status, csv_bytes = self.owner.call("GET", "/api/settlement/export")
        self.assertEqual(status, 200)
        self.assertTrue(csv_bytes.startswith("﻿".encode()))
        self.assertIn(b"Boost", csv_bytes)
        expected = report["expected_cash_cents"]
        status, closed = self.owner.call("POST", "/api/settlement/close", {"counted_cash": expected / 100 + 2, "note": "RM2 extra in drawer"})
        self.assertEqual((status, closed["variance_cents"]), (200, 200))
        self.assertEqual(self.today()["closing"]["counted_cash_cents"], expected + 200)
        self.assertEqual(self.staff.call("GET", "/api/settlement")[0], 403)
        self.assertEqual(self.owner.call("GET", "/api/settlement?day=yesterday")[0], 400)

    def test_tables_can_be_deactivated(self):
        _, table = self.owner.call("POST", "/api/tables", {"name": "Table 9"})
        self.owner.call("PUT", f"/api/tables/{table['id']}", {"active": False})
        self.assertEqual(self.guest.call("GET", f"/api/public/menu?table={table['code']}")[0], 404)
        self.assertEqual(self.staff.call("POST", "/api/tables", {"name": "x"})[0], 403)


if __name__ == "__main__":
    unittest.main()
