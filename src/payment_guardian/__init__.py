"""Payment Guardian: PayPal Sandbox reconciliation, anomaly detection and
human-approved actions with a tamper-evident audit log.

Safety invariants (enforced in code and tests):
* The PayPal client only talks to the PayPal *sandbox* host (or a loopback
  mock when explicitly enabled for tests). Live hosts are refused.
* The client exposes read/verify operations only; there is no code path that
  moves money.
* Remediation actions are *proposals*; they execute (as simulated local
  records) only after a named human approval, and every step is audit-logged.
"""

__version__ = "0.1.0"
