import unittest
from decimal import Decimal

from payment_guardian.models import normalise_paypal_transaction
from payment_guardian.payments_api import capture_to_detail, fetch_payment_details, refund_to_detail
from payment_guardian.reconcile import reconcile
from payment_guardian.models import LedgerEntry, parse_ts

CAP = {"id": "CAP0000000000001", "status": "PARTIALLY_REFUNDED", "invoice_id": "ORD-1",
       "amount": {"currency_code": "USD", "value": "45.00"}, "create_time": "2026-10-27T18:05:30Z",
       "seller_receivable_breakdown": {"paypal_fee": {"currency_code": "USD", "value": "2.06"}}}
REF = {"id": "REF0000000000001", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "15.00"},
       "create_time": "2026-10-27T18:10:00Z",
       "links": [{"rel": "up", "href": "https://api.sandbox.paypal.com/v2/payments/captures/CAP0000000000001"}]}


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_capture(self, i):
        self.calls.append(i); return CAP

    def get_refund(self, i):
        self.calls.append(i); return REF


class PaymentsApiTest(unittest.TestCase):
    def test_capture_maps(self):
        t = normalise_paypal_transaction(capture_to_detail(CAP))
        self.assertEqual((t.reference, t.amount, t.event_code, t.fee), ("ORD-1", Decimal("45.00"), "T0006", Decimal("2.06")))

    def test_refund_inherits_reference_and_is_negative(self):
        t = normalise_paypal_transaction(refund_to_detail(REF, {"CAP0000000000001": CAP}))
        self.assertEqual((t.reference, t.amount, t.event_code), ("ORD-1", Decimal("-15.00"), "T1107"))

    def test_partial_refund_no_finding_and_bounded(self):
        c = FakeClient()
        d = fetch_payment_details(c, ["CAP0000000000001"] * 60, ["REF0000000000001"], max_items=50)
        self.assertEqual(len(c.calls), 51)
        txns = [normalise_paypal_transaction(x) for x in d[:1] + d[-1:]]
        led = [LedgerEntry("ORD-1", Decimal("45.00"), "USD", "p", parse_ts("2026-10-27T18:00:00Z"))]
        codes = [f.code for f in reconcile(txns, led)]
        self.assertNotIn("REFUND_EXCEEDS_CAPTURE", codes)
        self.assertNotIn("AMOUNT_MISMATCH", codes)


if __name__ == "__main__":
    unittest.main()
