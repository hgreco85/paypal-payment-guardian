"""Reconcile PayPal transactions against the merchant ledger."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Dict, Iterable, List

from .models import Finding, LedgerEntry, Txn

PAYMENT_EVENTS = {"T0006", "T0000", "T0001"}   # captures / checkout payments
REFUND_EVENTS = {"T1107", "T1106"}


def _sev(score: int) -> str:
    return "HIGH" if score >= 75 else "MEDIUM" if score >= 40 else "LOW"


def _f(code: str, score: int, txns: List[Txn], ref, **detail) -> Finding:
    return Finding(code=code, severity=_sev(score), score=score,
                   txn_ids=sorted(t.txn_id for t in txns), reference=ref,
                   detail={k: (str(v) if isinstance(v, Decimal) else v) for k, v in detail.items()})


def reconcile(txns: Iterable[Txn], ledger: Iterable[LedgerEntry],
              *, amount_tolerance: Decimal = Decimal("0.00")) -> List[Finding]:
    """Deterministic reconciliation. Joins on Txn.reference == LedgerEntry.order_ref.

    Codes: AMOUNT_MISMATCH, CURRENCY_MISMATCH, ORPHAN_PAYPAL (no ledger order),
    ORPHAN_LEDGER (order never paid), DUPLICATE_CAPTURE (same reference captured
    more than once), REFUND_EXCEEDS_CAPTURE, STATUS_NOT_SETTLED.
    """
    led: Dict[str, LedgerEntry] = {e.order_ref: e for e in ledger}
    by_ref: Dict[str, List[Txn]] = defaultdict(list)
    findings: List[Finding] = []
    for t in txns:
        by_ref[t.reference].append(t)

    for ref, group in by_ref.items():
        payments = [t for t in group if t.event_code in PAYMENT_EVENTS and t.amount > 0]
        refunds = [t for t in group if t.event_code in REFUND_EVENTS]
        entry = led.get(ref)
        if not ref or entry is None:
            findings.append(_f("ORPHAN_PAYPAL", 70, group, ref or None,
                               reason="PayPal transaction without matching ledger order"))
            continue
        if len(payments) > 1:
            findings.append(_f("DUPLICATE_CAPTURE", 90, payments, ref,
                               count=len(payments), expected=entry.expected_amount))
        for p in payments[:1]:
            if p.currency != entry.currency:
                findings.append(_f("CURRENCY_MISMATCH", 85, [p], ref,
                                   paypal=p.currency, ledger=entry.currency))
            elif abs(p.amount - entry.expected_amount) > amount_tolerance:
                diff = p.amount - entry.expected_amount
                score = 80 if abs(diff) / max(entry.expected_amount, Decimal("0.01")) > Decimal("0.1") else 55
                findings.append(_f("AMOUNT_MISMATCH", score, [p], ref,
                                   paypal=p.amount, expected=entry.expected_amount, difference=diff))
            if p.status != "S":
                findings.append(_f("STATUS_NOT_SETTLED", 45, [p], ref, status=p.status))
        if refunds:
            captured = sum((p.amount for p in payments), Decimal("0"))
            refunded = sum((abs(r.amount) for r in refunds), Decimal("0"))
            if refunded > captured:
                findings.append(_f("REFUND_EXCEEDS_CAPTURE", 95, refunds + payments, ref,
                                   captured=captured, refunded=refunded))

    seen_refs = set(by_ref)
    for ref, entry in led.items():
        if ref not in seen_refs:
            findings.append(Finding("ORPHAN_LEDGER", "MEDIUM", 50, [], ref,
                                    {"reason": "ledger order has no PayPal transaction",
                                     "expected": str(entry.expected_amount)}))
    return sorted(findings, key=lambda f: (-f.score, f.code, f.reference or ""))
