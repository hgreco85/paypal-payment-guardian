# Submission answers (draft — do not submit without owner approval)

- **Deadline**: Thu 2026-11-12 12:00 PT (= 17:00 ART)
- **Public repo**: fresh public repo with detectable MIT LICENSE (single squashed commit, no secrets)
- **Demo video**: < 3:00, public on YouTube, English, no third-party music/logos

## Text description (draft)
Payment Guardian is an AI-assisted payment reconciliation and anomaly-review agent for the PayPal Sandbox.
It pulls transactions via Transaction Search, reconciles them against a merchant ledger, detects anomalies
(amount/currency mismatches, duplicate captures, orphans, refund abuse, velocity bursts), explains each finding
with a local Qwen model or a deterministic template, and requires a named human to approve any remediation.
Every step is recorded in a tamper-evident hash-chained audit log. USD 0 incremental cost.

## Evidence status
See `docs/EVIDENCE.md`: PayPal Sandbox calls (OAuth, Transaction Search, Orders/Payments) were executed against the real
Sandbox on 2026-10-27; offline tests use synthetic data and a local mock; explanations shown in the demo are deterministic templates.
