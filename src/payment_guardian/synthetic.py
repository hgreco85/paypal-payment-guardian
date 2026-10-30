"""Deterministic SYNTHETIC data in the PayPal Transaction Search response shape.

Everything produced here is fake and flagged: transaction ids start with
'SYN-' and payers are pseudonymous. Used for offline tests, the mock sandbox
and the demo. It is NOT data from PayPal.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from .models import LedgerEntry, parse_ts

BASE = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)


def _detail(tid, ref, amount, cur="USD", status="S", code="T0006", at=None, payer="payer-1", fee=None):
    at = at or BASE
    return {"transaction_info": {
        "transaction_id": tid, "invoice_id": ref, "transaction_event_code": code,
        "transaction_initiation_date": at.strftime("%Y-%m-%dT%H:%M:%S+0000"),
        "transaction_amount": {"currency_code": cur, "value": f"{Decimal(amount):.2f}"},
        "fee_amount": {"currency_code": cur, "value": f"-{(fee if fee is not None else (Decimal(amount) * Decimal('0.029') if Decimal(amount) > 0 else Decimal('0'))):.2f}"},
        "transaction_status": status},
        "payer_info": {"account_id": payer}}


def build_scenario(seed: int = 7) -> Tuple[List[Dict[str, Any]], List[LedgerEntry], Dict[str, str]]:
    """Returns (paypal_transaction_details, ledger, expected_codes_by_reference)."""
    rng = random.Random(seed)
    details: List[Dict[str, Any]] = []
    ledger: List[LedgerEntry] = []
    expected: Dict[str, str] = {}

    def add_ledger(ref, amount, payer, at, cur="USD"):
        ledger.append(LedgerEntry(ref, Decimal(amount), cur, payer, at))

    for i in range(1, 21):                               # 20 clean orders
        at = BASE + timedelta(hours=i * 3)
        amt = Decimal(rng.choice([19, 24, 29, 35, 42, 49, 55, 60])) + Decimal(rng.choice(["0.00", "0.50", "0.99"]))
        ref, payer = f"ORD-{1000 + i}", f"payer-{i}"
        details.append(_detail(f"SYN-T{i:04d}", ref, amt, at=at, payer=payer))
        add_ledger(ref, amt, payer, at)

    at = BASE + timedelta(days=3)
    details.append(_detail("SYN-MISM", "ORD-2001", "45.00", at=at, payer="payer-a"))
    add_ledger("ORD-2001", "54.00", "payer-a", at); expected["ORD-2001"] = "AMOUNT_MISMATCH"

    details.append(_detail("SYN-CUR", "ORD-2002", "30.00", cur="EUR", at=at, payer="payer-b"))
    add_ledger("ORD-2002", "30.00", "payer-b", at); expected["ORD-2002"] = "CURRENCY_MISMATCH"

    for k in (1, 2):                                       # duplicate capture
        details.append(_detail(f"SYN-DUP{k}", "ORD-2003", "80.00", at=at + timedelta(seconds=k * 20), payer="payer-c"))
    add_ledger("ORD-2003", "80.00", "payer-c", at); expected["ORD-2003"] = "DUPLICATE_CAPTURE"

    details.append(_detail("SYN-ORPH", "ORD-9999", "75.00", at=at, payer="payer-d"))   # paid, no order
    expected["ORD-9999"] = "ORPHAN_PAYPAL"

    add_ledger("ORD-2004", "40.00", "payer-e", at); expected["ORD-2004"] = "ORPHAN_LEDGER"   # order never paid

    details.append(_detail("SYN-PAY5", "ORD-2005", "60.00", at=at, payer="payer-f"))
    details.append(_detail("SYN-REF5", "ORD-2005", "-90.00", code="T1107", at=at + timedelta(hours=1), payer="payer-f"))
    add_ledger("ORD-2005", "60.00", "payer-f", at); expected["ORD-2005"] = "REFUND_EXCEEDS_CAPTURE"

    for k in range(5):                                     # velocity burst, one payer
        t2 = at + timedelta(minutes=k * 2)
        ref = f"ORD-31{k:02d}"
        details.append(_detail(f"SYN-VEL{k}", ref, "9.99", at=t2, payer="payer-bot"))
        add_ledger(ref, "9.99", "payer-bot", t2)
    expected["ORD-3103"] = "VELOCITY_BURST"

    details.append(_detail("SYN-BIG", "ORD-2006", "4500.00", at=at, payer="payer-g"))
    add_ledger("ORD-2006", "4500.00", "payer-g", at); expected["ORD-2006"] = "AMOUNT_OUTLIER"
    return details, ledger, expected


def response_page(details: List[Dict[str, Any]], page: int, page_size: int) -> Dict[str, Any]:
    pages = max(1, -(-len(details) // page_size))
    chunk = details[(page - 1) * page_size: page * page_size]
    return {"transaction_details": chunk, "total_items": len(details), "total_pages": pages, "page": page}
