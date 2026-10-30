"""Minimal PayPal *Sandbox* REST client (stdlib urllib, read/verify only).

Fail-closed host policy: only ``api-m.sandbox.paypal.com`` is accepted, plus a
loopback host when ``allow_loopback_mock=True`` (used by the local mock server
in the tests; clearly NOT PayPal). Live ``api-m.paypal.com`` is refused.

Credentials are read from environment variable *names*:
    PAYPAL_SANDBOX_CLIENT_ID, PAYPAL_SANDBOX_CLIENT_SECRET (and optionally
    PAYPAL_SANDBOX_WEBHOOK_ID for webhook signature verification).
Values are never logged, printed or included in exceptions.
"""
from __future__ import annotations

import base64
import json
import re
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.parse import urlparse

SANDBOX_HOST = "api-m.sandbox.paypal.com"
SANDBOX_BASE = "https://" + SANDBOX_HOST
ENV_CLIENT_ID = "PAYPAL_SANDBOX_CLIENT_ID"
ENV_CLIENT_SECRET = "PAYPAL_SANDBOX_CLIENT_SECRET"
ENV_WEBHOOK_ID = "PAYPAL_SANDBOX_WEBHOOK_ID"
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class SandboxPolicyError(RuntimeError):
    """Raised when a request would leave the sandbox (live host, bad scheme)."""


class PayPalApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"PayPal API error status={status}: {message}")
        self.status = status


def credentials_present(env: Optional[Dict[str, str]] = None) -> Dict[str, bool]:
    """Report presence (never values) of the sandbox credential variables."""
    e = os.environ if env is None else env
    return {n: bool(e.get(n)) for n in (ENV_CLIENT_ID, ENV_CLIENT_SECRET, ENV_WEBHOOK_ID)}


def assert_sandbox_url(url: str, *, allow_loopback_mock: bool = False) -> None:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host == SANDBOX_HOST and p.scheme == "https":
        return
    if allow_loopback_mock and host in _LOOPBACK and p.scheme == "http":
        return
    raise SandboxPolicyError(f"refused non-sandbox URL host={host!r} scheme={p.scheme!r}")


Transport = Callable[[str, str, Dict[str, str], Optional[bytes]], "tuple[int, bytes]"]


def _urllib_transport(method: str, url: str, headers: Dict[str, str], body: Optional[bytes]):
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (host policy-checked)
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class PayPalSandboxClient:
    def __init__(self, client_id: str, client_secret: str, *, base_url: str = SANDBOX_BASE,
                 allow_loopback_mock: bool = False, transport: Optional[Transport] = None,
                 max_retries: int = 2):
        assert_sandbox_url(base_url, allow_loopback_mock=allow_loopback_mock)
        self._id = client_id
        self._secret = client_secret
        self.base_url = base_url.rstrip("/")
        self._allow_mock = allow_loopback_mock
        self._transport = transport or _urllib_transport
        self._max_retries = max(0, min(int(max_retries), 3))  # bounded retries
        self._token: Optional[str] = None
        self._token_exp = 0.0
        self.calls: List[str] = []  # "METHOD path" audit of what was called (no secrets)
        self.call_log: List[str] = []  # "METHOD path -> HTTP status" (no query, no secrets)

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None, **kw) -> "PayPalSandboxClient":
        e = os.environ if env is None else env
        cid, sec = e.get(ENV_CLIENT_ID), e.get(ENV_CLIENT_SECRET)
        if not cid or not sec:
            raise PayPalApiError(0, "sandbox credentials not present in environment "
                                    f"({ENV_CLIENT_ID}/{ENV_CLIENT_SECRET})")
        return cls(cid, sec, **kw)

    # -- low level -------------------------------------------------------
    def _request(self, method: str, path: str, *, headers: Dict[str, str],
                 body: Optional[bytes] = None, query: Optional[Dict[str, str]] = None):
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        assert_sandbox_url(url, allow_loopback_mock=self._allow_mock)
        last: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self.calls.append(f"{method} {path}")
            status, raw = self._transport(method, url, headers, body)
            self.call_log.append(f"{method} {path} -> {status}")
            if status in (429, 500, 502, 503, 504) and attempt < self._max_retries:
                time.sleep(min(0.2 * (2 ** attempt), 1.0))
                continue
            if status >= 400:
                # message intentionally excludes headers/body of auth requests
                raise PayPalApiError(status, _safe_error(raw))
            return json.loads(raw.decode("utf-8") or "{}")
        raise PayPalApiError(0, f"exhausted retries: {last}")

    def _auth_headers(self) -> Dict[str, str]:
        if not self._token or time.time() > self._token_exp - 30:
            basic = base64.b64encode(f"{self._id}:{self._secret}".encode()).decode()
            data = self._request(
                "POST", "/v1/oauth2/token",
                headers={"Authorization": f"Basic {basic}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                body=b"grant_type=client_credentials")
            self._token = data["access_token"]
            self._token_exp = time.time() + int(data.get("expires_in", 300))
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    # -- read-only operations -------------------------------------------
    def search_transactions(self, start: str, end: str, *, page_size: int = 100,
                            max_pages: int = 10) -> Iterator[Dict[str, Any]]:
        """GET /v1/reporting/transactions (Transaction Search). Max 31-day window."""
        page = 1
        while page <= max_pages:
            data = self._request("GET", "/v1/reporting/transactions", headers=self._auth_headers(),
                                 query={"start_date": start, "end_date": end,
                                        "fields": "transaction_info,payer_info",
                                        "page_size": str(page_size), "page": str(page)})
            for item in data.get("transaction_details", []):
                yield item
            if page >= int(data.get("total_pages", 1)):
                return
            page += 1

    def _get_resource(self, kind: str, rid: str) -> Dict[str, Any]:
        if not re.fullmatch(r"[A-Z0-9]{8,30}", rid or ""):
            raise ValueError(f"invalid {kind} id")
        path = {"capture": "/v2/payments/captures/", "refund": "/v2/payments/refunds/",
                "order": "/v2/checkout/orders/"}[kind] + rid
        return self._request("GET", path, headers=self._auth_headers())

    def get_capture(self, capture_id: str) -> Dict[str, Any]:
        """GET /v2/payments/captures/{id} - read-only."""
        return self._get_resource("capture", capture_id)

    def get_refund(self, refund_id: str) -> Dict[str, Any]:
        """GET /v2/payments/refunds/{id} - read-only."""
        return self._get_resource("refund", refund_id)

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """GET /v1/notifications/webhooks - read-only authenticated smoke call."""
        return self._request("GET", "/v1/notifications/webhooks", headers=self._auth_headers()).get("webhooks", [])

    def verify_webhook_signature(self, *, webhook_id: str, headers: Dict[str, str],
                                 event: Dict[str, Any]) -> bool:
        """POST /v1/notifications/verify-webhook-signature -> SUCCESS/FAILURE."""
        h = {k.lower(): v for k, v in headers.items()}
        payload = {
            "auth_algo": h.get("paypal-auth-algo", ""),
            "cert_url": h.get("paypal-cert-url", ""),
            "transmission_id": h.get("paypal-transmission-id", ""),
            "transmission_sig": h.get("paypal-transmission-sig", ""),
            "transmission_time": h.get("paypal-transmission-time", ""),
            "webhook_id": webhook_id,
            "webhook_event": event,
        }
        data = self._request("POST", "/v1/notifications/verify-webhook-signature",
                             headers=self._auth_headers(), body=json.dumps(payload).encode())
        return data.get("verification_status") == "SUCCESS"


def _safe_error(raw: bytes) -> str:
    try:
        d = json.loads(raw.decode("utf-8"))
        return str(d.get("name") or d.get("error") or "error")[:80] + ": " + \
            str(d.get("message") or d.get("error_description") or "")[:160]
    except Exception:  # noqa: BLE001
        return "non-json error body"
