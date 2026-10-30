#!/usr/bin/env bash
# Reproducible demo, no credentials needed. Shows the three data modes honestly labelled.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
python3 -m payment_guardian check-creds || echo "(no sandbox creds in env: sandbox mode skipped, mock-http + synthetic still run)"
echo "== 1. SYNTHETIC offline =="; python3 -m payment_guardian demo --mode synthetic --out out --approve-all-high reviewer
echo "== 2. MOCK HTTP (local fake of PayPal endpoints; NOT PayPal) =="; python3 -m payment_guardian demo --mode mock-http --out out
echo "== 3. audit verification =="; python3 -m payment_guardian verify-audit out/audit-synthetic.jsonl
echo "== 4. tamper test =="; cp out/audit-synthetic.jsonl out/tampered.jsonl
sed -i '0,/HOLD_FOR_REVIEW/s//MONITOR/' out/tampered.jsonl; python3 -m payment_guardian verify-audit out/tampered.jsonl || echo "tamper detected (expected)"
if python3 -m payment_guardian check-creds >/dev/null 2>&1; then
  echo "== 5. LIVE SANDBOX =="; python3 -m payment_guardian demo --mode sandbox --ledger examples/ledger.sample.json --out out
fi
echo "report: out/report-synthetic.html"
