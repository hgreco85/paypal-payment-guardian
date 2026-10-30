import json, unittest
import _path  # noqa: F401
from payment_guardian.paypal_client import (PayPalSandboxClient, SandboxPolicyError, PayPalApiError,
                                            assert_sandbox_url, credentials_present)
from payment_guardian.mock_sandbox import start_mock
from payment_guardian.synthetic import build_scenario


class HostPolicy(unittest.TestCase):
    def test_live_host_refused(self):
        for url in ("https://api-m.paypal.com", "https://api.paypal.com", "https://evil.example.com",
                    "http://api-m.sandbox.paypal.com", "https://api-m.sandbox.paypal.com.evil.com"):
            with self.assertRaises(SandboxPolicyError, msg=url):
                PayPalSandboxClient("a", "b", base_url=url)

    def test_loopback_only_when_enabled(self):
        with self.assertRaises(SandboxPolicyError):
            assert_sandbox_url("http://127.0.0.1:9")
        assert_sandbox_url("http://127.0.0.1:9", allow_loopback_mock=True)
        assert_sandbox_url("https://api-m.sandbox.paypal.com/v1/x")

    def test_credentials_presence_reports_names_only(self):
        pres = credentials_present({"PAYPAL_SANDBOX_CLIENT_ID": "x"})
        self.assertEqual(pres, {"PAYPAL_SANDBOX_CLIENT_ID": True, "PAYPAL_SANDBOX_CLIENT_SECRET": False,
                                "PAYPAL_SANDBOX_WEBHOOK_ID": False})

    def test_from_env_missing_creds_raises_without_values(self):
        with self.assertRaises(PayPalApiError) as cm:
            PayPalSandboxClient.from_env({})
        self.assertNotIn("secret_value", str(cm.exception))


class OverMockHttp(unittest.TestCase):
    """MOCK: local loopback server, not PayPal."""
    def setUp(self):
        self.details, _, _ = build_scenario()

    def test_search_paginates_and_only_reads(self):
        srv, url, st = start_mock(self.details)
        try:
            c = PayPalSandboxClient("id", "SECRET-XYZ", base_url=url, allow_loopback_mock=True)
            got = list(c.search_transactions("2026-10-01T00:00:00-0000", "2026-10-31T00:00:00-0000", page_size=10))
        finally:
            srv.shutdown()
        self.assertEqual(len(got), len(self.details))
        methods = {(m, p) for m, p in st["calls"]}
        self.assertEqual(methods, {("POST", "/v1/oauth2/token"), ("GET", "/v1/reporting/transactions")})
        self.assertNotIn("SECRET-XYZ", " ".join(c.calls))

    def test_retry_on_503_then_success_bounded(self):
        srv, url, st = start_mock(self.details, fail_first=2)
        try:
            c = PayPalSandboxClient("id", "s", base_url=url, allow_loopback_mock=True, max_retries=2)
            self.assertTrue(list(c.search_transactions("a", "b")))
        finally:
            srv.shutdown()
        srv, url, st = start_mock(self.details, fail_first=99)
        try:
            c = PayPalSandboxClient("id", "s", base_url=url, allow_loopback_mock=True, max_retries=2)
            with self.assertRaises(PayPalApiError):
                list(c.search_transactions("a", "b"))
            self.assertEqual(sum(1 for m, p in st["calls"] if p == "/v1/reporting/transactions"), 3)
        finally:
            srv.shutdown()

    def test_retry_cap(self):
        c = PayPalSandboxClient("a", "b", max_retries=50)
        self.assertEqual(c._max_retries, 3)


if __name__ == "__main__":
    unittest.main()
