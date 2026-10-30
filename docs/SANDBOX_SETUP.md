# PayPal Sandbox setup (free)
1. Sign in at <https://developer.paypal.com/> → *Apps & Credentials* → **Sandbox** → *Create App* (Merchant).
2. In the app's *Features*, enable **Transaction Search** (needed for `/v1/reporting/transactions`). Sandbox data can take up to ~3 hours to appear.
3. Create transactions with sandbox buyer/merchant test accounts (Dashboard → *Testing Tools* → *Sandbox Accounts*, or any sandbox checkout).
4. Store `Client ID` and `Secret` in your secret manager and expose them to the process as
   `PAYPAL_SANDBOX_CLIENT_ID` and `PAYPAL_SANDBOX_CLIENT_SECRET`. For webhook verification also set `PAYPAL_SANDBOX_WEBHOOK_ID`.
5. Run `python -m payment_guardian check-creds` (presence only) then `demo --mode sandbox --ledger examples/ledger.sample.json`.
Never use live credentials: the client refuses any non-sandbox host.
