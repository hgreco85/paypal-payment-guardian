"""Domain models and PayPal payload normalisation (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional


def parse_ts(value: str) -> datetime:
    """Parse PayPal timestamps such as 2026-10-01T12:00:00+0000 / ...Z."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    if len(v) >= 5 and v[-5] in "+-" and v[-3] != ":":
        v = v[:-2] + ":" + v[-2:]
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid money amount: {value!r}") from exc


@dataclass(frozen=True)
class Txn:
    """A PayPal-side transaction (normalised)."""
    txn_id: str
    reference: str          # invoice_id / custom_id used to join with the ledger
    amount: Decimal
    currency: str
    status: str             # S=success, P=pending, D=denied, V=reversed
    event_code: str         # T0006 payment, T1107 refund, ...
    created: datetime
    payer: str              # pseudonymous payer key (never raw PII in reports)
    fee: Decimal = Decimal("0")
    synthetic: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["amount"] = str(self.amount)
        d["fee"] = str(self.fee)
        d["created"] = self.created.isoformat()
        return d


@dataclass(frozen=True)
class LedgerEntry:
    """Merchant-side expected payment (simulated ledger / order system)."""
    order_ref: str
    expected_amount: Decimal
    currency: str
    payer: str
    created: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {"order_ref": self.order_ref, "expected_amount": str(self.expected_amount),
                "currency": self.currency, "payer": self.payer,
                "created": self.created.isoformat()}


@dataclass
class Finding:
    code: str               # reason code, e.g. AMOUNT_MISMATCH
    severity: str           # LOW | MEDIUM | HIGH
    score: int              # 0-100
    txn_ids: List[str]
    reference: Optional[str]
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalise_paypal_transaction(item: Dict[str, Any], *, synthetic: bool = False) -> Txn:
    """Map one element of Transaction Search `transaction_details[]` to Txn.

    Field names follow the documented Transaction Search v1 response
    (`transaction_info.*`, `payer_info.*`).
    """
    info = item.get("transaction_info") or {}
    payer = item.get("payer_info") or {}
    amt = info.get("transaction_amount") or {}
    fee = info.get("fee_amount") or {}
    tid = info.get("transaction_id")
    if not tid:
        raise ValueError("transaction_info.transaction_id missing")
    ref = info.get("invoice_id") or info.get("custom_field") or info.get("paypal_reference_id") or ""
    payer_key = payer.get("account_id") or payer.get("email_address") or "unknown"
    return Txn(
        txn_id=str(tid),
        reference=str(ref),
        amount=to_decimal(amt.get("value", "0")),
        currency=str(amt.get("currency_code", "USD")),
        status=str(info.get("transaction_status", "S")),
        event_code=str(info.get("transaction_event_code", "T0000")),
        created=parse_ts(info["transaction_initiation_date"]),
        payer=str(payer_key),
        fee=abs(to_decimal(fee.get("value", "0"))),
        synthetic=synthetic,
    )
