# Public claims

Each claim below is limited to what the running code and tests currently show.

| Claim | Evidence |
| --- | --- |
| The public API is read-only for the browser | `frontend/src/app/api/read/[...path]/route.ts` rejects decision and job writes |
| A paper cycle can refuse without a fill | `tests/test_prefront.py` cycle refusal, `model_calls` recorded on the run |
| Caller-supplied price, book, fee, side, and risk context are rejected in production | `tests/test_adversarial.py` |
| A label-only book does not call the model | `tests/test_adversarial.py` |
| SEC EDGAR stays disabled until `T2_SEC_USER_AGENT` is set | `src/aftermath_api/sources/edgar.py` and ops status |
| A qualifying filing is required before a model call | `tests/test_events.py` |
| The model budget defaults to 3 calls per day | `AFTERMATH_LLM_MAX_CALLS_PER_DAY`, `src/aftermath_api/config.py` |
| Metrics stay `INSUFFICIENT_DATA` below the preregistered sample | `docs/PREREG_PRODUCTION_V1.md` |
| OpenTimestamps is not claimed as a confirmed Bitcoin anchor | receipt anchor state is pending or unconfirmed until a proof verifies |

Not claimed: a profitable edge, a completed live model fill, uninterrupted scheduler uptime, or a selected open-source license.
