"""Human approval gate. Actions are proposals until a named human decides.

There is deliberately NO real-money executor here: an approved action only
produces a *simulated* local record (e.g. "HOLD_FOR_REVIEW") and an audit
entry. Agents/AI can propose, never approve.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .audit import AuditLog
from .models import Finding

HUMAN_PREFIX = "human:"
ACTIONS = {"HIGH": "HOLD_FOR_REVIEW", "MEDIUM": "FLAG_FOR_FOLLOWUP", "LOW": "MONITOR"}


class ApprovalError(RuntimeError):
    pass


@dataclass
class Proposal:
    proposal_id: str
    action: str
    finding_code: str
    reference: Optional[str]
    severity: str
    status: str = "PENDING"          # PENDING | APPROVED | REJECTED
    decided_by: Optional[str] = None
    reason: Optional[str] = None
    executed_simulated: bool = False


class ApprovalGate:
    def __init__(self, audit: AuditLog):
        self.audit = audit
        self.proposals: Dict[str, Proposal] = {}

    def propose(self, finding: Finding, *, proposer: str = "agent:payment-guardian") -> Proposal:
        pid = hashlib.sha256(f"{finding.code}|{finding.reference}|{','.join(finding.txn_ids)}".encode()).hexdigest()[:12]
        if pid in self.proposals:                      # idempotent
            return self.proposals[pid]
        p = Proposal(pid, ACTIONS[finding.severity], finding.code, finding.reference, finding.severity)
        self.proposals[pid] = p
        self.audit.append(proposer, "action_proposed", {"proposal_id": pid, "action": p.action,
                          "code": p.finding_code, "reference": p.reference, "severity": p.severity})
        return p

    def decide(self, proposal_id: str, *, approver: str, approve: bool, reason: str = "") -> Proposal:
        p = self.proposals.get(proposal_id)
        if p is None:
            raise ApprovalError("unknown proposal")
        if not approver.startswith(HUMAN_PREFIX) or len(approver) <= len(HUMAN_PREFIX):
            self.audit.append(approver or "unknown", "approval_denied_non_human", {"proposal_id": proposal_id})
            raise ApprovalError("only a named human approver (human:<name>) may decide")
        if p.status != "PENDING":
            raise ApprovalError(f"proposal already {p.status}")
        p.status = "APPROVED" if approve else "REJECTED"
        p.decided_by, p.reason = approver, reason
        self.audit.append(approver, "action_approved" if approve else "action_rejected",
                          {"proposal_id": proposal_id, "reason": reason})
        if approve:
            p.executed_simulated = True           # simulated local record only
            self.audit.append("system:simulator", "action_executed_simulated",
                              {"proposal_id": proposal_id, "action": p.action, "real_money_moved": False})
        return p

    def pending(self) -> List[Proposal]:
        return [p for p in self.proposals.values() if p.status == "PENDING"]
