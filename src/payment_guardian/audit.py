"""Tamper-evident audit log: append-only JSONL, SHA-256 hash chain.

Each record: {seq, ts, actor, event, data, prev_hash, hash}. `verify_chain`
recomputes every hash; any edit, deletion or reorder is detected. Optional
HMAC (key from env/secret manager) can be layered on top by the caller.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GENESIS = "0" * 64


def _digest(rec: Dict[str, Any]) -> str:
    body = {k: rec[k] for k in ("seq", "ts", "actor", "event", "data", "prev_hash")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path, *, clock=None):
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash, self._seq = GENESIS, 0
        if self.path.exists():
            ok, msg = verify_chain(self.path)
            if not ok:
                raise ValueError(f"refusing to append to corrupted audit log: {msg}")
            for rec in read_records(self.path):
                self._last_hash, self._seq = rec["hash"], rec["seq"]

    def append(self, actor: str, event: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rec = {"seq": self._seq + 1, "ts": self._clock(), "actor": actor, "event": event,
               "data": data or {}, "prev_hash": self._last_hash}
        rec["hash"] = _digest(rec)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        self._last_hash, self._seq = rec["hash"], rec["seq"]
        return rec


def read_records(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def verify_chain(path: Path) -> Tuple[bool, str]:
    prev, expected_seq = GENESIS, 1
    try:
        recs = read_records(path)
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"unreadable: {exc}"
    for rec in recs:
        if rec.get("seq") != expected_seq:
            return False, f"sequence gap at seq={rec.get('seq')} (expected {expected_seq})"
        if rec.get("prev_hash") != prev:
            return False, f"broken link at seq={rec['seq']}"
        if _digest(rec) != rec.get("hash"):
            return False, f"hash mismatch at seq={rec['seq']}"
        prev, expected_seq = rec["hash"], expected_seq + 1
    return True, f"ok records={len(recs)} head={prev[:16]}"
