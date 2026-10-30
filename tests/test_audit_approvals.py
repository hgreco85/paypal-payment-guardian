import json, tempfile, unittest
from pathlib import Path
import _path  # noqa: F401
from payment_guardian.audit import AuditLog, verify_chain
from payment_guardian.approvals import ApprovalGate, ApprovalError
from payment_guardian.models import Finding


def mk(tmp):
    return AuditLog(Path(tmp) / "a.jsonl", clock=lambda: "2026-10-27T00:00:00+00:00")


class Audit(unittest.TestCase):
    def test_chain_verifies_and_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = mk(tmp)
            for i in range(5):
                a.append("t", "e", {"i": i})
            self.assertTrue(verify_chain(a.path)[0])
            b = mk(tmp); b.append("t", "e", {"i": 5})
            self.assertEqual(verify_chain(a.path), (True, verify_chain(a.path)[1]))
            self.assertIn("records=6", verify_chain(a.path)[1])

    def test_tamper_delete_reorder_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = mk(tmp)
            for i in range(4):
                a.append("t", "e", {"i": i})
            lines = a.path.read_text().splitlines()
            # edit
            recs = [json.loads(l) for l in lines]; recs[1]["data"]["i"] = 99
            a.path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in recs) + "\n")
            self.assertFalse(verify_chain(a.path)[0])
            # delete
            a.path.write_text("\n".join(lines[:1] + lines[2:]) + "\n")
            self.assertFalse(verify_chain(a.path)[0])
            # reorder
            a.path.write_text("\n".join([lines[1], lines[0]] + lines[2:]) + "\n")
            self.assertFalse(verify_chain(a.path)[0])

    def test_refuses_append_to_corrupt_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = mk(tmp); a.append("t", "e")
            a.path.write_text(a.path.read_text().replace('"e"', '"x"'))
            with self.assertRaises(ValueError):
                mk(tmp)


F = Finding("AMOUNT_MISMATCH", "HIGH", 80, ["T1"], "R1", {})


class Approvals(unittest.TestCase):
    def test_only_named_human_can_decide(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = ApprovalGate(mk(tmp)); p = g.propose(F)
            for who in ("agent:payment-guardian", "", "human:", "system:x", "reviewer"):
                with self.assertRaises(ApprovalError):
                    g.decide(p.proposal_id, approver=who, approve=True)
            self.assertEqual(p.status, "PENDING"); self.assertFalse(p.executed_simulated)

    def test_approve_executes_simulated_only_and_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = mk(tmp); g = ApprovalGate(a); p = g.propose(F)
            g.decide(p.proposal_id, approver="human:reviewer", approve=True, reason="confirmed")
            self.assertTrue(p.executed_simulated)
            ev = [json.loads(l)["event"] for l in a.path.read_text().splitlines()]
            self.assertEqual(ev, ["action_proposed", "action_approved", "action_executed_simulated"])
            self.assertIn('"real_money_moved": false', a.path.read_text())
            with self.assertRaises(ApprovalError):
                g.decide(p.proposal_id, approver="human:reviewer", approve=False)

    def test_reject_never_executes_and_propose_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = ApprovalGate(mk(tmp)); p = g.propose(F); self.assertIs(g.propose(F), p)
            g.decide(p.proposal_id, approver="human:ana", approve=False)
            self.assertFalse(p.executed_simulated); self.assertEqual(g.pending(), [])


if __name__ == "__main__":
    unittest.main()
