"""LIVE PayPal Sandbox smoke test. Skipped unless sandbox credentials are in the
environment (inject with your secret manager; never commit them).

    PAYPAL_SANDBOX_CLIENT_ID / PAYPAL_SANDBOX_CLIENT_SECRET
Read-only: OAuth token + Transaction Search for the last 7 days.
"""
import os, sys, pathlib, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from datetime import datetime, timedelta, timezone
from payment_guardian.paypal_client import PayPalApiError, PayPalSandboxClient, SANDBOX_BASE

HAVE = bool(os.environ.get("PAYPAL_SANDBOX_CLIENT_ID") and os.environ.get("PAYPAL_SANDBOX_CLIENT_SECRET"))


@unittest.skipUnless(HAVE, "PAYPAL_SANDBOX_CLIENT_ID/SECRET not set - live sandbox test SKIPPED (not passed)")
class Live(unittest.TestCase):
    def test_oauth_and_authenticated_read(self):
        c = PayPalSandboxClient.from_env(base_url=SANDBOX_BASE)
        self.assertIsInstance(c.list_webhooks(), list)
        self.assertIn("POST /v1/oauth2/token -> 200", c.call_log)
        self.assertIn("GET /v1/notifications/webhooks -> 200", c.call_log)

    def test_transaction_search(self):
        c = PayPalSandboxClient.from_env(base_url=SANDBOX_BASE)
        end = datetime.now(timezone.utc); start = end - timedelta(days=7)
        fmt = "%Y-%m-%dT%H:%M:%S-0000"
        try:
            items = list(c.search_transactions(start.strftime(fmt), end.strftime(fmt), max_pages=1))
        except PayPalApiError as e:
            if e.status == 403:
                self.skipTest("OWNER ACTION: Transaction Search not enabled for this sandbox app (HTTP 403 NOT_AUTHORIZED)")
            raise
        self.assertIsInstance(items, list)       # may be empty on a fresh sandbox
        self.assertIn("GET /v1/reporting/transactions -> 200", c.call_log)


if __name__ == "__main__":
    unittest.main()
