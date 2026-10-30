"""CLI: python -m payment_guardian <check-creds|demo|verify-audit>"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .audit import verify_chain
from .explain import Explainer
from .paypal_client import PayPalApiError, PayPalSandboxClient, credentials_present
from .pipeline import fetch_details, run_pipeline
from .synthetic import build_scenario


def load_ledger(path: Path):
    from datetime import datetime
    from decimal import Decimal
    from .models import LedgerEntry
    rows = json.loads(path.read_text())
    return [LedgerEntry(r["order_ref"], Decimal(str(r["expected_amount"])), r["currency"],
                        r.get("payer", ""), datetime.fromisoformat(r["created"])) for r in rows]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="payment_guardian")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-creds", help="report presence (never values) of sandbox env vars")
    d = sub.add_parser("demo")
    d.add_argument("--mode", choices=["synthetic", "mock-http", "sandbox", "sandbox-payments"], default="synthetic")
    d.add_argument("--out", default="out")
    d.add_argument("--start", default="2026-10-01T00:00:00-0000")
    d.add_argument("--end", default="2026-10-31T00:00:00-0000")
    d.add_argument("--ledger", help="JSON file: [{order_ref, expected_amount, currency, payer, created}] (required for --mode sandbox)")
    d.add_argument("--payment-ids", help='JSON file {"captures":[ids],"refunds":[ids]} for --mode sandbox-payments')
    d.add_argument("--approve-all-high", metavar="NAME", help="simulate human:NAME approving HIGH findings (demo only)")
    v = sub.add_parser("verify-audit"); v.add_argument("path")
    a = ap.parse_args(argv)

    if a.cmd == "check-creds":
        pres = credentials_present()
        print(json.dumps(pres, indent=2))
        return 0 if pres["PAYPAL_SANDBOX_CLIENT_ID"] and pres["PAYPAL_SANDBOX_CLIENT_SECRET"] else 2
    if a.cmd == "verify-audit":
        ok, msg = verify_chain(Path(a.path)); print(("OK " if ok else "FAIL ") + msg); return 0 if ok else 1

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    audit_path = out / f"audit-{a.mode}.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    details, ledger, expected = build_scenario()
    if a.mode in ("sandbox", "sandbox-payments"):
        if not a.ledger:
            print("sandbox mode needs --ledger <file.json> (see examples/ledger.sample.json)", file=sys.stderr)
            return 2
        ledger = load_ledger(Path(a.ledger))
        try:
            client = PayPalSandboxClient.from_env()
            if a.mode == "sandbox-payments":
                from .payments_api import fetch_payment_details
                if not a.payment_ids:
                    print("sandbox-payments mode needs --payment-ids <file.json>", file=sys.stderr)
                    return 2
                ids = json.loads(Path(a.payment_ids).read_text())
                details = fetch_payment_details(client, ids.get("captures", []), ids.get("refunds", []))
            else:
                details = fetch_details(client, a.start, a.end)
        except PayPalApiError as e:
            print(f"SANDBOX ERROR: {e}", file=sys.stderr)
            if getattr(e, "status", 0) == 403:
                print("OWNER ACTION: enable 'Transaction Search' for this sandbox app (developer.paypal.com > "
                      "Apps & Credentials > app > Features), then retry.", file=sys.stderr)
            return 3
        mode = "SANDBOX_LIVE_PAYMENTS_API" if a.mode == "sandbox-payments" else "SANDBOX_LIVE"
        synthetic = False
        print("live calls: " + ", ".join(client.call_log), file=sys.stderr)
    elif a.mode == "mock-http":
        from .mock_sandbox import start_mock
        srv, url, _ = start_mock(details)
        client = PayPalSandboxClient("mock", "mock", base_url=url, allow_loopback_mock=True)
        details = fetch_details(client, a.start, a.end); srv.shutdown()
        mode, synthetic = "MOCK_HTTP", True
    else:
        mode, synthetic = "SYNTHETIC_OFFLINE", True
    res, gate = run_pipeline(details=details, ledger=ledger, audit_path=audit_path, mode=mode,
                             explainer=Explainer(), synthetic=synthetic)
    if a.approve_all_high:
        for p in list(gate.proposals.values()):
            if p.severity == "HIGH":
                gate.decide(p.proposal_id, approver=f"human:{a.approve_all_high}", approve=True,
                            reason="demo approval")
        res.proposals = [p.__dict__ for p in gate.proposals.values()]
        res.audit_ok, res.audit_msg = verify_chain(audit_path)
    (out / f"report-{a.mode}.json").write_text(json.dumps(res.__dict__, indent=2, default=str))
    from .report_html import render
    render(out / f"report-{a.mode}.json", out / f"report-{a.mode}.html")
    print(f"mode={res.mode} txns={res.txn_count} findings={len(res.findings)} "
          f"proposals={len(res.proposals)} audit={'OK' if res.audit_ok else 'FAIL'} ({res.audit_msg})")
    for f in res.findings[:12]:
        print(f"  [{f['severity']:<6}] {f['code']:<24} ref={f['reference']} :: {f['explanation']['text'][:110]}")
    return 0
