"""Rule + robust-statistics anomaly detection over PayPal transactions."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from statistics import median
from typing import Iterable, List

from .models import Finding, Txn
from .reconcile import PAYMENT_EVENTS, _f


def detect_anomalies(txns: Iterable[Txn], *, mad_threshold: float = 6.0,
                     velocity_window: timedelta = timedelta(minutes=10),
                     velocity_count: int = 4) -> List[Finding]:
    """Detect AMOUNT_OUTLIER (modified z-score on MAD), VELOCITY_BURST (many
    payments from one payer in a short window) and ROUND_AMOUNT_SPIKE."""
    pay = sorted((t for t in txns if t.event_code in PAYMENT_EVENTS and t.amount > 0),
                 key=lambda t: t.created)
    out: List[Finding] = []
    if len(pay) >= 8:
        vals = [float(t.amount) for t in pay]
        med = median(vals)
        mad = median(abs(v - med) for v in vals)
        if mad > 0:
            for t in pay:
                mz = 0.6745 * (float(t.amount) - med) / mad
                if mz > mad_threshold:
                    out.append(_f("AMOUNT_OUTLIER", min(99, 60 + int(mz)), [t], t.reference or None,
                                  amount=t.amount, median=Decimal(str(med)), modified_z=round(mz, 2)))
    by_payer = defaultdict(list)
    for t in pay:
        by_payer[t.payer].append(t)
    for payer, items in by_payer.items():
        i = 0
        for j in range(len(items)):
            while items[j].created - items[i].created > velocity_window:
                i += 1
            window = items[i:j + 1]
            if len(window) >= velocity_count:
                out.append(_f("VELOCITY_BURST", 80, window, window[-1].reference or None,
                              payer_key=payer[:4] + "***", count=len(window),
                              window_minutes=int(velocity_window.total_seconds() // 60)))
                break
    big_round = [t for t in pay if t.amount >= 1000 and t.amount % 500 == 0]
    for t in big_round:
        out.append(_f("ROUND_AMOUNT_SPIKE", 40, [t], t.reference or None, amount=t.amount))
    # de-duplicate identical (code, txn set)
    seen, uniq = set(), []
    for f in out:
        k = (f.code, tuple(f.txn_ids))
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return sorted(uniq, key=lambda f: (-f.score, f.code))
