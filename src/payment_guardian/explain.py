"""AI explanations for findings.

Order of preference (all $0): local Ollama (Qwen) -> deterministic template.
The local model is only used when the single local inference slot is idle
(`/api/ps` reports no loaded model) and PG_LLM=ollama is set, so Payment
Guardian never competes with another job for the slot. The LLM can only
*explain*; it cannot decide, approve or execute. Every explanation records its
`source` and fallback reason, and LLM output is validated before use.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable, Dict, Optional

from .models import Finding

TEMPLATES = {
    "AMOUNT_MISMATCH": "PayPal captured {paypal} but the ledger expected {expected} (difference {difference}). Possible tampering, partial payment or pricing bug.",
    "CURRENCY_MISMATCH": "PayPal currency {paypal} differs from ledger currency {ledger}. Amount comparison is unsafe until a human confirms the intended currency.",
    "DUPLICATE_CAPTURE": "{count} captures share one order reference (expected total {expected}). Likely double-charge or webhook replay.",
    "ORPHAN_PAYPAL": "A PayPal transaction has no matching ledger order. Possible unrecorded sale, mis-tagged reference or unauthorised payment.",
    "ORPHAN_LEDGER": "A ledger order has no PayPal transaction (expected {expected}). Payment may be pending, abandoned or lost.",
    "REFUND_EXCEEDS_CAPTURE": "Refunds ({refunded}) exceed captured funds ({captured}). Possible refund abuse or reconciliation gap.",
    "STATUS_NOT_SETTLED": "Transaction status is {status}, not settled. Do not fulfil the order until it settles.",
    "AMOUNT_OUTLIER": "Amount {amount} is far above the typical payment (median {median}, robust z={modified_z}). Verify with the payer.",
    "VELOCITY_BURST": "{count} payments from one payer within {window_minutes} minutes (payer {payer_key}). Possible card-testing or scripted abuse.",
    "ROUND_AMOUNT_SPIKE": "Large round-number payment {amount}. Low-confidence signal; review alongside other findings.",
}

Http = Callable[[str, Optional[bytes]], bytes]


def _http(url: str, body: Optional[bytes]) -> bytes:
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - loopback only, checked below
        return r.read()


def deterministic_explanation(f: Finding) -> str:
    tpl = TEMPLATES.get(f.code, "Anomaly {code}; review manually.")
    try:
        return tpl.format(code=f.code, **f.detail)
    except (KeyError, IndexError):
        return f"{f.code}: {json.dumps(f.detail, sort_keys=True)}"


class Explainer:
    def __init__(self, *, mode: Optional[str] = None, host: str = "http://127.0.0.1:11434",
                 model: Optional[str] = None, http: Optional[Http] = None):
        self.mode = (mode or os.environ.get("PG_LLM", "deterministic")).lower()
        self.host = host.rstrip("/")
        if not (self.host.startswith("http://127.0.0.1") or self.host.startswith("http://localhost")):
            raise ValueError("LLM host must be loopback (local model only, $0)")
        self.model = model or os.environ.get("PG_LLM_MODEL", "qwen3.5:4b")
        self._http = http or _http
        self.llm_calls = 0

    def _slot_idle(self) -> bool:
        try:
            ps = json.loads(self._http(self.host + "/api/ps", None).decode())
        except Exception:  # noqa: BLE001
            return False
        return not ps.get("models")

    def explain(self, f: Finding) -> Dict[str, Any]:
        base = deterministic_explanation(f)
        if self.mode != "ollama":
            return {"text": base, "source": "deterministic", "fallback_reason": "llm_disabled"}
        if not self._slot_idle():
            return {"text": base, "source": "deterministic", "fallback_reason": "resource_busy_or_unreachable"}
        prompt = ("You are a payments risk analyst. In at most 2 sentences, explain this finding to a "
                  "finance reviewer and say what to check. Do not invent facts. Finding code: "
                  f"{f.code}. Facts: {json.dumps(f.detail, sort_keys=True)}. Draft: {base}")
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "think": False,
                           "options": {"temperature": 0, "num_predict": 120}}).encode()
        try:
            out = json.loads(self._http(self.host + "/api/generate", body).decode())
            text = " ".join(str(out.get("response", "")).split())
            self.llm_calls += 1
        except Exception:  # noqa: BLE001
            return {"text": base, "source": "deterministic", "fallback_reason": "llm_error"}
        if not (10 <= len(text) <= 600):
            return {"text": base, "source": "deterministic", "fallback_reason": "llm_output_rejected"}
        return {"text": text, "source": f"ollama:{self.model}", "fallback_reason": None}
