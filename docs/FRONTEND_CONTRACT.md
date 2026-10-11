# Frontend contract

The browser does not call Render directly with a decision, job, model, signing, or database credential.

The same-origin proxy is `frontend/src/app/api/read/[...path]/route.ts`. It holds only the reader token in `AFTERMATH_API_TOKEN` and may forward:

- `GET /health`
- `GET /ready`
- `GET /v1/events`
- `GET /v1/events/{id}`
- `GET /v1/decisions`
- `GET /v1/decisions/{id}`
- `GET /v1/instruments/{symbol}`
- `GET /v1/evidence/{id}`
- `GET /v1/paper/fills`
- `GET /v1/receipts/{id}`
- `POST /v1/receipts/{id}/verify`
- `POST /v1/receipts/{id}/replay`
- `GET /v1/ops/status`
- `GET /v1/metrics`

It must reject `POST /v1/decisions`, `POST /v1/events`, and `/internal/*` before those requests reach Render. `GET /v1/metrics` is `INSUFFICIENT_DATA` until this service has graded paper outcomes. `ots_status=pending` is not a Bitcoin confirmation. Replay reports `llm_reproduction=not_available` because a later model call is not a reproduction of the signed decision.

Reads return `{items, next_cursor}` when they are lists. An empty list is a successful empty state, not an error. `401` means the reader token is missing or wrong. `403` means a reader or job token was used on a route that requires a different token. `404` means the id is absent. `422` is a schema or evidence error. `503` means the service is up but not ready to append.

`contracts/openapi.json` is exported from the running application. Regenerate it from `app.openapi()` and require the bytes to match.
