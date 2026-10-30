# Architecture

```
PayPal Sandbox ──► paypal_client (OAuth, Transaction Search, verify-webhook) ──► models.normalise
 (or MOCK / SYNTHETIC)                                                              │
                                                                                    ▼
 merchant ledger ───────────────────────────────────────────────────────► reconcile + anomaly
                                                                                    │ findings
                                                                                    ▼
                                         explain (Ollama/Qwen if idle, else template) ──► approvals (proposal)
                                                                                    │            ▲ human:<name>
                                                                                    ▼            │
                                                                   audit (SHA-256 hash chain, JSONL)
```
* **Fail-closed network policy**: `assert_sandbox_url` accepts only the sandbox host over HTTPS (loopback HTTP only for tests).
* **No write path to money**: the client has no payment/refund/payout methods.
* **Bounded retries**: at most 3 retries with capped backoff on 429/5xx.
* **LLM boundary**: input = reason code + numeric facts (payer keys masked); output validated; model cannot trigger actions.
* **Audit**: each record hashes `{seq, ts, actor, event, data, prev_hash}`; verification recomputes the chain.
