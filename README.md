# AFTERMATH

Paper-only evidence service. It records market observations, evidence, model or abstention decisions, risk refusals, and paper fills. It does not place live orders and it does not claim a profit result.

## Run

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
set PYTHONPATH=src
.venv\Scripts\python -m aftermath_api
```

Copy `.env.example` to `.env` and fill the local values. The process prints `SET` or `MISSING` for each setting. It does not print secret values.

`GET /health` and `GET /ready` need no token. Other reads need `AFTERMATH_API_TOKEN`. `POST /v1/decisions` needs `AFTERMATH_DECISION_TOKEN`. `POST /internal/jobs/paper-cycle` needs `AFTERMATH_JOB_TOKEN`.

If the model key is absent, the process still starts and `POST /v1/decisions` records `ABSTAIN` with `decision_source=abstain`. In production, a missing database URL stops the process before it binds. A missing signing key leaves `/ready` unavailable and refuses appends.

SEC live requests stay off until `T2_SEC_USER_AGENT` is a real contact string.

The frontend lives in `frontend/` and is a Next.js application. Its dashboard reads the API through `/api/read`, which forwards only the reader allowlist and attaches the reader token on the server. The landing preview is labeled sample data and is not the ledger. `GET /v1/metrics` remains `INSUFFICIENT_DATA` until graded paper outcomes exist.

The paper cycle fetches Bitget public order books. A usable book without a qualifying filing or news event records `ABSTAIN` / `no_qualifying_event`. A missing book, a spread above 12 bp, or depth below 1000 USDT inside 25 bp records that specific refusal. The cycle does not call the model and does not create a fill. SEC requests stay off until `T2_SEC_USER_AGENT` is a real contact string. There is no project `LICENSE` file.

`POST /internal/jobs/paper-cycle` fetches the whitelisted Bitget tickers when it is invoked outside the test environment. A ticker without an order book is stored as evidence and the cycle records `ABSTAIN` / `missing_order_book`. It does not call the model and it does not create a paper fill. The same UTC hour is idempotent. GitHub Actions calls that route hourly when `AFTERMATH_JOB_TOKEN` is configured. A failed cycle fails the workflow; an empty or failed fetch is `source_unavailable`, not a trade.

`GET /v1/metrics` returns `INSUFFICIENT_DATA` until graded paper outcomes exist. This service does not publish a profitability score. `GET /v1/ops/status` shows the latest cycle. Receipt `ots_status=pending` means the OpenTimestamps anchor is not confirmed.

No license file is present for this project's own code. Public visibility is not a license grant. Vendored research code keeps its `NOTICE`.

Tests: `pytest -q` runs the offline suite. Live Bitget and Postgres tests are marked and are not part of that default command.
