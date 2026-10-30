# Payment Guardian

**An AI-assisted payment reconciliation and anomaly-review agent built on the PayPal Developer Platform (Sandbox).**
Built for the PayPal AI Hackathon. Python 3.10+, **zero third-party dependencies**, MIT licensed.

> **Safety first.** Payment Guardian never moves money. The PayPal client is read/verify-only and hard-refuses any
> host except `api-m.sandbox.paypal.com`. Remediation actions are *proposals* that only a **named human** can approve,
> and every step lands in a tamper-evident, hash-chained audit log.

## The problem
Merchants discover payment problems late: double captures from webhook replays, amounts that do not match the order,
currency mix-ups, refunds larger than the sale, card-testing bursts. Finance teams reconcile by spreadsheet and gut feeling.

## What it does
| Capability | How |
|---|---|
| **PayPal Sandbox integration** | OAuth2 client-credentials, Transaction Search (`/v1/reporting/transactions`, paged), webhook verification (`/v1/notifications/verify-webhook-signature`) |
| **Reconciliation** | Joins PayPal transactions to your ledger by order reference: `AMOUNT_MISMATCH`, `CURRENCY_MISMATCH`, `DUPLICATE_CAPTURE`, `ORPHAN_PAYPAL`, `ORPHAN_LEDGER`, `REFUND_EXCEEDS_CAPTURE`, `STATUS_NOT_SETTLED` |
| **Anomaly detection** | Robust (MAD-based) amount outliers, per-payer velocity bursts, round-amount spikes |
| **Explanations** | Deterministic templates by default; optional local Ollama/Qwen (no cloud, $0) can rephrase them when available. The model only *explains*; it cannot approve or act. Output is length/validity-checked. |
| **Human approvals** | Findings create proposals (`HOLD_FOR_REVIEW`, ...). Only `human:<name>` can approve/reject. Approval produces a *simulated* record, never a payment. |
| **Verifiable audit** | Append-only JSONL, SHA-256 hash chain; `verify-audit` detects edits, deletions and reordering |
| **Idempotency** | Webhook events deduplicated by event id; proposals are idempotent per finding |

## Quick start (no credentials needed)
```bash
git clone <this repo URL> && cd paypal-payment-guardian
bash scripts/demo.sh                   # synthetic + local mock + audit verify + tamper test
python3 -m unittest discover -s tests  # 36 offline tests (1 live test skipped without creds)
open out/report-synthetic.html         # visual report
```

## Run against the real PayPal Sandbox
1. Create a Sandbox REST app at <https://developer.paypal.com/> and enable **Transaction Search** for it (see `docs/SANDBOX_SETUP.md`).
2. Provide credentials through your secret manager as environment variables (never commit them):
   `PAYPAL_SANDBOX_CLIENT_ID`, `PAYPAL_SANDBOX_CLIENT_SECRET` (optional `PAYPAL_SANDBOX_WEBHOOK_ID`).
3. ```bash
   PYTHONPATH=src python3 -m payment_guardian check-creds          # reports presence only, never values
   PYTHONPATH=src python3 -m payment_guardian demo --mode sandbox --ledger examples/ledger.sample.json  # your ledger vs live sandbox data
   PYTHONPATH=src python3 -m unittest discover -s tests/live -v    # live smoke test (skipped without creds)
   ```

## Evidence (Sandbox vs synthetic vs deterministic)
Real PayPal **Sandbox** runs (OAuth 200, Transaction Search 200 with 6 transactions, 4 captures, a partial refund, AMOUNT_MISMATCH and VELOCITY_BURST findings, audit chain OK) are documented in [`docs/EVIDENCE.md`](docs/EVIDENCE.md). Offline tests and the default demo use **synthetic** data. The 2026-10-30 Sandbox run used a **real local LLM** (Qwen2.5-1.5B via Ollama) for explanations; earlier runs and offline tests use the **deterministic template fallback**, and every explanation is labelled with its `source`.

## Honest labelling of data sources
Every report carries its `mode`: `SANDBOX_LIVE` (real sandbox API), `MOCK_HTTP` (a local fake of the PayPal endpoints
used to exercise the real HTTP code path offline - **not PayPal**), or `SYNTHETIC_OFFLINE` (generated data, ids prefixed `SYN-`).

## Enable local AI explanations
```bash
ollama pull qwen2.5:1.5b   # any small local model works
PG_LLM=ollama PG_LLM_MODEL=qwen2.5:1.5b PYTHONPATH=src python3 -m payment_guardian demo --mode synthetic
```
The explainer only talks to loopback, checks `/api/ps` first and falls back to templates if the model slot is busy.

## Layout
`src/payment_guardian/` library & CLI · `tests/` offline tests (+`tests/live/`) · `docs/` architecture, sandbox setup, video script · `scripts/` demo, sanitiser, exporter.

## License
MIT (see `LICENSE`). Not affiliated with or endorsed by PayPal. Uses only the public Sandbox APIs.
