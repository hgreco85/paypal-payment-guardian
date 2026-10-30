"""End-to-end pipeline: fetch -> normalise -> reconcile + detect -> explain ->
propose -> (human decision) with full audit trail."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .anomaly import detect_anomalies
from .approvals import ApprovalGate
from .audit import AuditLog, verify_chain
from .explain import Explainer
from .models import Finding, LedgerEntry, Txn, normalise_paypal_transaction
from .paypal_client import PayPalSandboxClient
from .reconcile import reconcile


@dataclass
class RunResult:
    mode: str                       # SANDBOX_LIVE | MOCK_HTTP | SYNTHETIC_OFFLINE
    txn_count: int
    findings: List[Dict[str, Any]]
    proposals: List[Dict[str, Any]]
    audit_path: str
    audit_ok: bool
    audit_msg: str


def run_pipeline(*, details: Iterable[Dict[str, Any]], ledger: List[LedgerEntry], audit_path: Path,
                 mode: str, explainer: Optional[Explainer] = None,
                 synthetic: bool = False) -> "tuple[RunResult, ApprovalGate]":
    audit = AuditLog(audit_path)
    gate = ApprovalGate(audit)
    explainer = explainer or Explainer()
    txns: List[Txn] = []
    for d in details:
        try:
            txns.append(normalise_paypal_transaction(d, synthetic=synthetic))
        except ValueError as exc:
            audit.append("system:ingest", "transaction_rejected", {"error": str(exc)})
    audit.append("system:ingest", "transactions_ingested", {"count": len(txns), "mode": mode})
    findings: List[Finding] = reconcile(txns, ledger) + detect_anomalies(txns)
    out_findings = []
    for f in sorted(findings, key=lambda x: (-x.score, x.code)):
        exp = explainer.explain(f)
        audit.append("agent:payment-guardian", "finding_explained",
                     {"code": f.code, "reference": f.reference, "score": f.score,
                      "explanation_source": exp["source"], "fallback_reason": exp["fallback_reason"]})
        gate.propose(f)
        out_findings.append({**f.to_dict(), "explanation": exp})
    ok, msg = verify_chain(audit_path)
    res = RunResult(mode, len(txns), out_findings, [p.__dict__ for p in gate.proposals.values()],
                    str(audit_path), ok, msg)
    return res, gate


def fetch_details(client: PayPalSandboxClient, start: str, end: str) -> List[Dict[str, Any]]:
    return list(client.search_transactions(start, end))
