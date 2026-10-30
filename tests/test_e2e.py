"""E2E over the full stack. Transport = MOCK loopback server (NOT PayPal)."""
import json, tempfile, unittest
from pathlib import Path
import _path  # noqa: F401
from payment_guardian.audit import verify_chain
from payment_guardian.mock_sandbox import start_mock
from payment_guardian.paypal_client import PayPalSandboxClient
from payment_guardian.pipeline import run_pipeline, fetch_details
from payment_guardian.explain import Explainer
from payment_guardian.synthetic import build_scenario
from payment_guardian.cli import main


class E2E(unittest.TestCase):
    def test_full_flow_mock_http(self):
        details, ledger, expected = build_scenario()
        srv, url, _ = start_mock(details)
        try:
            c = PayPalSandboxClient("i", "s", base_url=url, allow_loopback_mock=True)
            got = fetch_details(c, "a", "b")
        finally:
            srv.shutdown()
        with tempfile.TemporaryDirectory() as tmp:
            ap = Path(tmp) / "a.jsonl"
            res, gate = run_pipeline(details=got, ledger=ledger, audit_path=ap, mode="MOCK_HTTP",
                                     explainer=Explainer(mode="deterministic"), synthetic=True)
            codes = {(f["reference"], f["code"]) for f in res.findings}
            for ref, code in expected.items():
                self.assertIn((ref, code), codes)
            self.assertTrue(res.audit_ok)
            self.assertTrue(all(p["status"] == "PENDING" and not p["executed_simulated"] for p in res.proposals))
            high = [p for p in gate.proposals.values() if p.severity == "HIGH"]
            gate.decide(high[0].proposal_id, approver="human:test", approve=True)
            self.assertTrue(verify_chain(ap)[0])

    def test_cli_modes_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ("synthetic", "mock-http"):
                self.assertEqual(main(["demo", "--mode", mode, "--out", tmp, "--approve-all-high", "tester"]), 0)
                self.assertEqual(main(["verify-audit", str(Path(tmp) / f"audit-{mode}.jsonl")]), 0)
                rep = json.loads((Path(tmp) / f"report-{mode}.json").read_text())
                self.assertIn(rep["mode"], ("SYNTHETIC_OFFLINE", "MOCK_HTTP"))

    def test_live_sandbox_not_claimed_without_creds(self):
        import os
        if os.environ.get("PAYPAL_SANDBOX_CLIENT_ID") and os.environ.get("PAYPAL_SANDBOX_CLIENT_SECRET"):
            self.skipTest("creds present: see tests/live/")
        with self.assertRaises(Exception):
            PayPalSandboxClient.from_env({})


if __name__ == "__main__":
    unittest.main()
