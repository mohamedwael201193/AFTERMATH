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

The frontend is not in this repository. It will be supplied separately and must not receive the decision token, job token, model key, signing key, or database URL.
