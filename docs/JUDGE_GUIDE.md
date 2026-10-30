# Judge guide — Payment Guardian (PayPal AI Hackathon)

## Run locally (no credentials)
```bash
git clone <repo> && cd payment-guardian
bash scripts/demo.sh                  # synthetic + mock HTTP + audit verify + tamper test
python3 -m unittest discover -s tests # 35 offline tests
open out/report-synthetic.html         # visual report
```

## What it shows
1. `check-creds` reports credential presence only (no values).
2. Synthetic demo: reconciliation + anomaly findings → AI explanations → proposals.
3. Mock HTTP demo: real PayPal HTTP code path against a local fake (labelled MOCK_HTTP).
4. `verify-audit` passes; tampered copy fails.

## Real PayPal Sandbox (optional)
Set `PAYPAL_SANDBOX_CLIENT_ID`, `PAYPAL_SANDBOX_CLIENT_SECRET` (and optionally `PAYPAL_SANDBOX_WEBHOOK_ID`) from your secret manager, then:
```bash
PYTHONPATH=src python3 -m payment_guardian check-creds
PYTHONPATH=src python3 -m payment_guardian demo --mode sandbox --ledger examples/ledger.sample.json
PYTHONPATH=src python3 -m unittest discover -s tests/live -v
```
The client refuses any non-sandbox host; no money is moved.

## Safety
- Read/verify only; no payment/refund/payout methods.
- Remediation actions are proposals approved by a named human.
- Every step is in a SHA-256 hash-chained audit log.
- Sanitiser: `python scripts/sanitize_check.py .` → OK.