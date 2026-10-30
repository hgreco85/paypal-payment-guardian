import json, tempfile, unittest
from pathlib import Path
import _path  # noqa: F401
from payment_guardian.audit import AuditLog
from payment_guardian.webhook import WebhookProcessor, WebhookRejected
from payment_guardian.paypal_client import PayPalSandboxClient
from payment_guardian.mock_sandbox import start_mock
from payment_guardian.explain import Explainer, deterministic_explanation
from payment_guardian.models import Finding

HDR = {"PayPal-Transmission-Id": "1", "PayPal-Transmission-Time": "t", "PayPal-Transmission-Sig": "GOOD",
       "PayPal-Cert-Url": "https://x", "PayPal-Auth-Algo": "SHA256withRSA"}
EV = {"id": "WH-1", "event_type": "PAYMENT.CAPTURE.COMPLETED"}


class Webhook(unittest.TestCase):
    """Signature verification here goes to the MOCK server, not PayPal."""
    def _wp(self, tmp, **kw):
        srv, url, _ = start_mock([], **kw)
        self.addCleanup(srv.shutdown)
        c = PayPalSandboxClient("i", "s", base_url=url, allow_loopback_mock=True)
        return WebhookProcessor(c, "WHID", AuditLog(Path(tmp) / "a.jsonl"))

    def test_accept_then_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = self._wp(tmp)
            self.assertEqual(w.process(HDR, EV), "accepted")
            self.assertEqual(w.process(HDR, EV), "duplicate")

    def test_invalid_signature_and_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = self._wp(tmp)
            with self.assertRaises(WebhookRejected):
                w.process({**HDR, "PayPal-Transmission-Sig": "BAD"}, EV)
            with self.assertRaises(WebhookRejected):
                w.process({}, EV)
            with self.assertRaises(WebhookRejected):
                w.process(HDR, {"event_type": "x"})
            self.assertNotIn("WH-1", w.seen)

    def test_verification_outage_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = PayPalSandboxClient("i", "s", base_url="http://127.0.0.1:1", allow_loopback_mock=True, max_retries=0,
                                    transport=lambda *a: (503, b"{}"))
            w = WebhookProcessor(c, "W", AuditLog(Path(tmp) / "a.jsonl"))
            with self.assertRaises(WebhookRejected):
                w.process(HDR, EV)


F = Finding("AMOUNT_MISMATCH", "HIGH", 80, ["T1"], "R1", {"paypal": "45.00", "expected": "54.00", "difference": "-9.00"})


class Explain(unittest.TestCase):
    def test_default_deterministic(self):
        r = Explainer(mode="deterministic").explain(F)
        self.assertEqual(r["source"], "deterministic"); self.assertIn("45.00", r["text"])

    def test_busy_slot_falls_back_without_generate_call(self):
        calls = []
        def http(url, body):
            calls.append(url); return json.dumps({"models": [{"name": "other-job-model:7b"}]}).encode()
        r = Explainer(mode="ollama", http=http).explain(F)
        self.assertEqual(r["fallback_reason"], "resource_busy_or_unreachable")
        self.assertTrue(all(u.endswith("/api/ps") for u in calls))

    def test_own_model_resident_still_uses_llm(self):
        def http(url, body):
            if url.endswith("/api/ps"): return json.dumps({"models": [{"name": "qwen3.5:4b"}]}).encode()
            return json.dumps({"response": "The capture is 9.00 below the order total; check for partial payment."}).encode()
        e = Explainer(mode="ollama", model="qwen3.5:4b", http=http); r = e.explain(F)
        self.assertTrue(r["source"].startswith("ollama:")); self.assertEqual(e.llm_calls, 1)

    def test_idle_slot_uses_llm_mocked(self):
        def http(url, body):
            if url.endswith("/api/ps"): return b'{"models": []}'
            return json.dumps({"response": "The capture is 9.00 below the order total; check for partial payment."}).encode()
        e = Explainer(mode="ollama", http=http); r = e.explain(F)
        self.assertTrue(r["source"].startswith("ollama:")); self.assertEqual(e.llm_calls, 1)

    def test_bad_llm_output_rejected(self):
        def http(url, body):
            if url.endswith("/api/ps"): return b'{"models": []}'
            return b'{"response": "ok"}'
        self.assertEqual(Explainer(mode="ollama", http=http).explain(F)["fallback_reason"], "llm_output_rejected")

    def test_llm_error_falls_back(self):
        def http(url, body):
            if url.endswith("/api/ps"): return b'{"models": []}'
            raise OSError("boom")
        self.assertEqual(Explainer(mode="ollama", http=http).explain(F)["fallback_reason"], "llm_error")

    def test_non_loopback_host_refused(self):
        with self.assertRaises(ValueError):
            Explainer(mode="ollama", host="https://api.openai.com")


if __name__ == "__main__":
    unittest.main()
