"""Phase 3 reconciliation tests — fake Etsy + Printify clients."""

from __future__ import annotations

from etsyshop.orders import reconcile


class FakeEtsy:
    def __init__(self, receipts, authorized=True):
        self._receipts = receipts
        self.is_authorized = authorized

    def list_receipts(self):
        return {"results": self._receipts}


class FakePrintify:
    def __init__(self, orders):
        self._orders = orders

    def list_orders(self):
        return {"data": self._orders}


def test_matched_order_no_issue():
    etsy = FakeEtsy([{"receipt_id": 1001, "name": "#1001", "is_paid": True, "is_shipped": False}])
    printify = FakePrintify([{"id": "p1", "status": "in-production",
                              "metadata": {"shop_order_label": "#1001"}}])
    report = reconcile(etsy, printify)
    assert report.matched == 1
    assert report.ok
    assert report.etsy_receipt_count == 1
    assert report.printify_order_count == 1


def test_stuck_printify_order_flagged():
    etsy = FakeEtsy([])
    printify = FakePrintify([{"id": "p2", "status": "had-issues", "metadata": {}}])
    report = reconcile(etsy, printify)
    assert not report.ok
    assert any(i.source == "printify" and "stuck" in i.reason for i in report.issues)


def test_unexpected_printify_status_flagged():
    etsy = FakeEtsy([])
    printify = FakePrintify([{"id": "p3", "status": "frobnicated", "metadata": {}}])
    report = reconcile(etsy, printify)
    assert any("unexpected status" in i.reason for i in report.issues)


def test_paid_unshipped_receipt_without_printify_match_flagged():
    etsy = FakeEtsy([{"receipt_id": 2002, "name": "#2002", "is_paid": True, "is_shipped": False}])
    printify = FakePrintify([])
    report = reconcile(etsy, printify)
    assert report.matched == 0
    assert any(i.source == "etsy" and "no matching" in i.reason for i in report.issues)


def test_shipped_receipt_without_match_is_not_flagged():
    etsy = FakeEtsy([{"receipt_id": 3003, "name": "#3003", "is_paid": True, "is_shipped": True}])
    report = reconcile(etsy, FakePrintify([]))
    assert report.ok


def test_unauthorized_etsy_skips_receipts():
    etsy = FakeEtsy([{"receipt_id": 1}], authorized=False)
    report = reconcile(etsy, FakePrintify([]))
    assert report.etsy_receipt_count == 0
