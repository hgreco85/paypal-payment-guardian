import unittest
import _path  # noqa: F401
from decimal import Decimal
from payment_guardian.models import normalise_paypal_transaction as norm
from payment_guardian.reconcile import reconcile
from payment_guardian.anomaly import detect_anomalies
from payment_guardian.synthetic import build_scenario, _detail, BASE
from payment_guardian.models import LedgerEntry


class Scenario(unittest.TestCase):
    def setUp(self):
        d, self.ledger, self.expected = build_scenario()
        self.txns = [norm(x, synthetic=True) for x in d]

    def test_every_injected_issue_found_with_exact_code(self):
        found = {(f.reference, f.code) for f in reconcile(self.txns, self.ledger) + detect_anomalies(self.txns)}
        for ref, code in self.expected.items():
            self.assertIn((ref, code), found, f"missing {code} for {ref}")

    def test_no_findings_on_clean_orders(self):
        clean = [t for t in self.txns if t.reference.startswith("ORD-10")]
        led = [e for e in self.ledger if e.order_ref.startswith("ORD-10")]
        self.assertEqual(reconcile(clean, led), [])
        self.assertEqual(detect_anomalies(clean), [])

    def test_deterministic(self):
        a = [f.to_dict() for f in reconcile(self.txns, self.ledger)]
        b = [f.to_dict() for f in reconcile(list(reversed(self.txns)), self.ledger)]
        self.assertEqual(a, b)

    def test_tolerance(self):
        d = [_detail("T1", "R1", "10.00")]
        led = [LedgerEntry("R1", Decimal("10.01"), "USD", "p", BASE)]
        t = [norm(x) for x in d]
        self.assertEqual(len(reconcile(t, led)), 1)
        self.assertEqual(reconcile(t, led, amount_tolerance=Decimal("0.05")), [])

    def test_pending_status_flagged(self):
        t = [norm(_detail("T1", "R1", "10.00", status="P"))]
        led = [LedgerEntry("R1", Decimal("10.00"), "USD", "p", BASE)]
        self.assertEqual([f.code for f in reconcile(t, led)], ["STATUS_NOT_SETTLED"])

    def test_malformed_transaction_rejected(self):
        with self.assertRaises(ValueError):
            norm({"transaction_info": {}})
        with self.assertRaises(ValueError):
            bad = _detail("T1", "R1", "1.00"); bad["transaction_info"]["transaction_amount"]["value"] = "abc"
            norm(bad)

    def test_small_sample_no_outlier_false_positive(self):
        t = [norm(_detail(f"T{i}", f"R{i}", "5000.00" if i == 0 else "10.00")) for i in range(5)]
        self.assertFalse([f for f in detect_anomalies(t) if f.code == "AMOUNT_OUTLIER"])


if __name__ == "__main__":
    unittest.main()
