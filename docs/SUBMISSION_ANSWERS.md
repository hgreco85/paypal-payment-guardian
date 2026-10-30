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
Sandbox on 2026-10-27 and 2026-10-30; offline tests use synthetic data and a local mock.
AI explanations: the 2026-10-30 Sandbox run (`examples/evidence/sandbox-run-2026-10-30/report-sandbox.json`) used a real local model, `ollama:qwen2.5:1.5b`, for the two explained findings (`source` and `fallback_reason` recorded per finding). The 2026-10-27 runs used the deterministic template fallback. Reproduce with `ollama pull qwen2.5:1.5b` and `PG_LLM=ollama PG_LLM_MODEL=qwen2.5:1.5b`; the code default model is `qwen3.5:4b` only when `PG_LLM_MODEL` is unset.
