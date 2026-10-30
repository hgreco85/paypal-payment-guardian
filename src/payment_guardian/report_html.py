"""Static HTML report (no JS, no external assets) for demos and screenshots."""
from __future__ import annotations

import html
import json
from pathlib import Path

CSS = """body{font:15px system-ui,sans-serif;margin:32px;background:#0b1220;color:#e6edf7}
h1{margin:0 0 4px}.sub{color:#8da2c0;margin-bottom:20px}.badge{padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
.HIGH{background:#7f1d1d;color:#fecaca}.MEDIUM{background:#78350f;color:#fde68a}.LOW{background:#1e3a5f;color:#bfdbfe}
table{border-collapse:collapse;width:100%}th,td{padding:8px 10px;border-bottom:1px solid #22324d;text-align:left;vertical-align:top}
th{color:#8da2c0;font-weight:600}.ok{color:#86efac}.bad{color:#fca5a5}.mode{background:#1f2a44;padding:6px 10px;border-radius:6px;display:inline-block}
code{color:#93c5fd}"""


def render(report_json: Path, out_html: Path) -> None:
    r = json.loads(Path(report_json).read_text())
    props = {(p["finding_code"], p["reference"]): p for p in r["proposals"]}
    rows = []
    for f in r["findings"]:
        p = props.get((f["code"], f["reference"]), {})
        rows.append(
            f"<tr><td><span class='badge {f['severity']}'>{f['severity']}</span> {f['score']}</td>"
            f"<td><code>{html.escape(f['code'])}</code></td><td>{html.escape(str(f['reference']))}</td>"
            f"<td>{html.escape(f['explanation']['text'])}<br><small>source: {html.escape(f['explanation']['source'])}"
            f"{' (fallback: ' + html.escape(str(f['explanation']['fallback_reason'])) + ')' if f['explanation']['fallback_reason'] else ''}</small></td>"
            f"<td>{html.escape(p.get('action', '-'))}<br><small>{html.escape(p.get('status', '-'))}"
            f"{' by ' + html.escape(p['decided_by']) if p.get('decided_by') else ''}"
            f"{' · simulated' if p.get('executed_simulated') else ''}</small></td></tr>")
    audit = "<span class='ok'>chain verified</span>" if r["audit_ok"] else "<span class='bad'>CHAIN BROKEN</span>"
    out_html.write_text(f"""<!doctype html><meta charset=utf-8><title>Payment Guardian report</title><style>{CSS}</style>
<h1>Payment Guardian</h1><div class=sub>PayPal reconciliation &amp; anomaly review · human approval required · no real money moves</div>
<p><span class=mode>data source: {html.escape(r['mode'])}</span> &nbsp; transactions: {r['txn_count']} &nbsp; findings: {len(r['findings'])}
&nbsp; audit log: {audit} <small>({html.escape(r['audit_msg'])})</small></p>
<table><tr><th>Risk</th><th>Reason code</th><th>Order ref</th><th>AI / rule explanation</th><th>Action (human gate)</th></tr>{''.join(rows)}</table>""")
