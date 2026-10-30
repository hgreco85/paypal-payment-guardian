"""Reconcile from Payments v2 resources (captures/refunds) fetched by id.

Transaction Search can lag hours behind; this read-only path maps capture and
refund objects into the Transaction Search `transaction_details` shape so the
same reconciliation runs immediately. Event codes: capture -> T0006, refund -> T1107.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _up_capture_id(refund: Dict[str, Any]) -> Optional[str]:
    for link in refund.get("links", []):
        if link.get("rel") == "up" and "/captures/" in link.get("href", ""):
            return link["href"].rstrip("/").rsplit("/", 1)[-1]
    return None


def _fee(obj: Dict[str, Any], key: str) -> Dict[str, str]:
    bd = obj.get(key) or {}
    f = bd.get("paypal_fee") or {}
    return {"currency_code": f.get("currency_code", "USD"), "value": f"-{f.get('value', '0')}"}


def capture_to_detail(c: Dict[str, Any]) -> Dict[str, Any]:
    amt = c.get("amount") or {}
    return {"transaction_info": {
        "transaction_id": c["id"], "invoice_id": c.get("invoice_id") or c.get("custom_id") or "",
        "transaction_event_code": "T0006",
        "transaction_initiation_date": c["create_time"],
        "transaction_amount": {"currency_code": amt.get("currency_code", "USD"), "value": amt.get("value", "0")},
        "fee_amount": _fee(c, "seller_receivable_breakdown"),
        "transaction_status": "S" if c.get("status") in ("COMPLETED", "PARTIALLY_REFUNDED", "REFUNDED") else "P"},
        "payer_info": {"account_id": "capture-api"}}


def refund_to_detail(r: Dict[str, Any], captures_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    amt = r.get("amount") or {}
    parent = captures_by_id.get(_up_capture_id(r) or "", {})
    ref = parent.get("invoice_id") or r.get("invoice_id") or ""
    return {"transaction_info": {
        "transaction_id": r["id"], "invoice_id": ref, "transaction_event_code": "T1107",
        "transaction_initiation_date": r["create_time"],
        "transaction_amount": {"currency_code": amt.get("currency_code", "USD"), "value": f"-{amt.get('value', '0')}"},
        "fee_amount": {"currency_code": amt.get("currency_code", "USD"), "value": "0.00"},
        "transaction_status": "S" if r.get("status") == "COMPLETED" else "P"},
        "payer_info": {"account_id": "capture-api"}}


def fetch_payment_details(client, capture_ids: Iterable[str], refund_ids: Iterable[str] = (),
                          *, max_items: int = 50) -> List[Dict[str, Any]]:
    caps = {}
    for cid in list(capture_ids)[:max_items]:
        caps[cid] = client.get_capture(cid)
    out = [capture_to_detail(c) for c in caps.values()]
    for rid in list(refund_ids)[:max_items]:
        out.append(refund_to_detail(client.get_refund(rid), caps))
    return out
