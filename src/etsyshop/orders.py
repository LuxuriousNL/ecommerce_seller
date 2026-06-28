"""Phase 3: order operations.

Printify auto-fulfills orders that arrive through its Etsy integration, so the
job here is monitoring, not fulfillment: pull orders from both sides, reconcile
them, and surface anything stuck or unmatched that needs a human.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from etsyshop.clients.etsy import EtsyClient
from etsyshop.clients.printify import PrintifyClient

# Printify order statuses that mean "nothing is wrong, leave it alone".
HEALTHY_PRINTIFY = {"in-production", "fulfilled", "shipped", "on-hold", "canceled"}
# Printify statuses that warrant attention.
STUCK_PRINTIFY = {"payment-not-received", "had-issues", "action-required"}


@dataclass
class OrderIssue:
    source: str  # "printify" or "etsy"
    order_id: str
    reason: str
    detail: str = ""


@dataclass
class ReconciliationReport:
    etsy_receipt_count: int = 0
    printify_order_count: int = 0
    matched: int = 0
    issues: list[OrderIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _printify_external_key(order: dict) -> str | None:
    """The Etsy-side identifier Printify stores for a synced order, if any."""
    meta = order.get("metadata") or {}
    return meta.get("shop_order_id") or meta.get("shop_order_label") or None


def reconcile(etsy: EtsyClient, printify: PrintifyClient) -> ReconciliationReport:
    """Cross-check Etsy receipts against Printify orders; flag exceptions."""
    report = ReconciliationReport()

    receipts = (etsy.list_receipts().get("results") or []) if etsy.is_authorized else []
    printify_orders = printify.list_orders().get("data") or []
    report.etsy_receipt_count = len(receipts)
    report.printify_order_count = len(printify_orders)

    # Index Printify orders by the Etsy identifier they carry.
    by_external: dict[str, dict] = {}
    for order in printify_orders:
        key = _printify_external_key(order)
        if key:
            by_external[str(key)] = order

        status = (order.get("status") or "").lower()
        if status in STUCK_PRINTIFY:
            report.issues.append(
                OrderIssue("printify", str(order.get("id")), f"stuck: {status}")
            )
        elif status and status not in HEALTHY_PRINTIFY:
            report.issues.append(
                OrderIssue("printify", str(order.get("id")), f"unexpected status: {status}")
            )

    # Every paid Etsy receipt should have a matching Printify order.
    for receipt in receipts:
        rid = str(receipt.get("receipt_id"))
        candidates = {rid, str(receipt.get("order_id", "")), receipt.get("name", "")}
        if any(c and c in by_external for c in candidates):
            report.matched += 1
            continue
        if receipt.get("is_paid") and not receipt.get("is_shipped"):
            report.issues.append(
                OrderIssue(
                    "etsy", rid, "paid but no matching Printify order",
                    "may not have synced to Printify yet",
                )
            )

    return report
