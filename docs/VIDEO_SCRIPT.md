# Demo video script (target 2:40, hard limit < 3:00; English; no music, no third-party logos)
| Time | Screen | Voice-over |
|---|---|---|
| 0:00-0:15 | Title card + problem | "Payment teams find double charges, wrong amounts and refund abuse days late. Payment Guardian finds them from PayPal data and keeps a human in control." |
| 0:15-0:35 | Terminal: `check-creds`, then `demo --mode sandbox` | "It connects to the PayPal Sandbox with OAuth, pulls transactions through Transaction Search, and refuses any non-sandbox host." |
| 0:35-1:05 | Terminal output of findings | "Reconciliation against the ledger flags amount and currency mismatches, duplicate captures, orphans and refunds above the sale. Anomaly detection adds outliers and velocity bursts." |
| 1:05-1:30 | HTML report (`out/report-*.html`) | "Each finding gets a plain-language explanation. A local Qwen model writes it when the slot is free; otherwise a deterministic template. The model never decides." |
| 1:30-2:00 | `demo --approve-all-high reviewer` (named-human approval) | "Every proposed action waits for a named human. Approving creates a simulated record only: no money moves." |
| 2:00-2:25 | `verify-audit` OK, then tamper + FAIL | "Every step is in a hash-chained audit log. Edit one byte and verification fails." |
| 2:25-2:40 | Repo + tests (35 passing) + license | "Open source, MIT, zero dependencies, fully reproducible. Payment Guardian: PayPal data, AI explanations, human control." |
Recording notes: record the real sandbox run only when live credentials are available; label any MOCK/SYNTHETIC scene on screen.
Upload to YouTube as public only after owner approval.
