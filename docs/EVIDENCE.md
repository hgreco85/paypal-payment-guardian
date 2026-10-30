# Evidence and data-source labelling

Payment Guardian distinguishes three kinds of evidence. Nothing below involves real money; all PayPal calls target `api-m.sandbox.paypal.com`.

| Label | What it is | Evidence |
|---|---|---|
| **SANDBOX (authentic)** | Real calls to the PayPal **Sandbox** REST APIs with a Sandbox app | 2026-10-27: `POST /v1/oauth2/token` → 200 (token scope includes `reporting/search/read`); 4 Sandbox orders captured (201 COMPLETED ×4); 1 partial refund of USD 15.00 (201 COMPLETED); `GET /v1/reporting/transactions` → 200 returning 6 transactions; `demo --mode sandbox` → mode=SANDBOX_LIVE, findings incl. `AMOUNT_MISMATCH` (ORD-2002: PayPal 85.00 vs ledger 80.00) and `VELOCITY_BURST` (ORD-2004, 4 payments from one payer in 10 min), audit chain OK. 2026-10-30: read-only re-run, `POST /v1/oauth2/token` → 200, `GET /v1/reporting/transactions` → 200, txns=6, audit OK. Live tests `tests/live/` pass when Sandbox credentials are present. |
| **SYNTHETIC / MOCK** | Generated data (ids prefixed `SYN-`) and a local fake of PayPal endpoints (`MOCK_HTTP`) used by the offline tests and demo | `python3 -m unittest discover -s tests` → 35 tests, OK (1 skipped: live test without creds). Demo: 33 txns → 9 findings → 9 proposals; tamper test detects a modified audit record. **Not PayPal data.** |
| **DETERMINISTIC explanations** | Template explanations generated from finding fields | Used in all recorded runs and in the demo video. An optional local LLM (Ollama) can rephrase explanations when available; it was **not** used for the published evidence and never approves or executes anything. |

Sandbox transaction ids (Sandbox only, not real payments): captures `3LR498133B080220K`, `65G514356C421233T`, `4NS49385VD756462Y`, `8GL23147BR176773V`; refund `3TX67761X8008443U`. Payer identifiers are masked in all reports.
