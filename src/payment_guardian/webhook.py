"""Webhook intake: structural validation, signature verification, idempotency."""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from .audit import AuditLog
from .paypal_client import PayPalSandboxClient

REQUIRED_HEADERS = ("paypal-transmission-id", "paypal-transmission-time",
                    "paypal-transmission-sig", "paypal-cert-url", "paypal-auth-algo")


class WebhookRejected(ValueError):
    pass


class WebhookProcessor:
    def __init__(self, client: PayPalSandboxClient, webhook_id: str, audit: AuditLog):
        self.client, self.webhook_id, self.audit = client, webhook_id, audit
        self.seen: Set[str] = set()

    def process(self, headers: Dict[str, str], event: Dict[str, Any]) -> str:
        """Returns 'accepted' or 'duplicate'; raises WebhookRejected otherwise.
        Signature is verified through PayPal's verify-webhook-signature API;
        an unverifiable event is never trusted (fail closed)."""
        h = {k.lower(): v for k, v in headers.items()}
        missing = [k for k in REQUIRED_HEADERS if not h.get(k)]
        if missing or not event.get("id") or not event.get("event_type"):
            self.audit.append("system:webhook", "webhook_rejected_malformed", {"missing": missing})
            raise WebhookRejected("malformed webhook")
        eid = str(event["id"])
        if eid in self.seen:
            self.audit.append("system:webhook", "webhook_duplicate_ignored", {"event_id": eid})
            return "duplicate"
        try:
            ok = self.client.verify_webhook_signature(webhook_id=self.webhook_id, headers=h, event=event)
        except Exception as exc:  # noqa: BLE001 - fail closed on any verification error
            self.audit.append("system:webhook", "webhook_verification_error", {"event_id": eid, "error": type(exc).__name__})
            raise WebhookRejected("signature verification unavailable") from exc
        if not ok:
            self.audit.append("system:webhook", "webhook_signature_invalid", {"event_id": eid})
            raise WebhookRejected("invalid signature")
        self.seen.add(eid)
        self.audit.append("system:webhook", "webhook_accepted", {"event_id": eid, "event_type": event["event_type"]})
        return "accepted"
