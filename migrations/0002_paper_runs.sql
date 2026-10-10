CREATE TABLE IF NOT EXISTS aftermath.paper_runs (
  id text PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE,
  status text NOT NULL,
  reason text,
  decision_id text,
  started_at_utc timestamptz NOT NULL,
  finished_at_utc timestamptz,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb
);
