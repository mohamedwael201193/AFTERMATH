CREATE SCHEMA IF NOT EXISTS aftermath;

CREATE TABLE IF NOT EXISTS aftermath.events (
  id text PRIMARY KEY,
  instrument_id text NOT NULL,
  event_type text NOT NULL,
  event_time_utc timestamptz NOT NULL,
  fetched_at_utc timestamptz NOT NULL,
  source text NOT NULL,
  schema_version int NOT NULL,
  payload jsonb NOT NULL,
  payload_hash text NOT NULL,
  mapping_confidence numeric,
  conflict boolean NOT NULL DEFAULT false,
  created_at_utc timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS aftermath.evidence (
  id text PRIMARY KEY,
  event_id text NOT NULL REFERENCES aftermath.events(id),
  schema_version int NOT NULL,
  payload_hash text NOT NULL,
  included_at_utc timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS aftermath.decisions (
  id text PRIMARY KEY,
  status text NOT NULL,
  decision_source text NOT NULL CHECK (decision_source IN ('model', 'abstain')),
  prompt_hash text,
  input_snapshot_hash text NOT NULL,
  schema_version int NOT NULL,
  reason text,
  idempotency_key text UNIQUE,
  created_at_utc timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS aftermath.decision_evidence (
  decision_id text NOT NULL REFERENCES aftermath.decisions(id),
  evidence_id text NOT NULL REFERENCES aftermath.evidence(id),
  position int NOT NULL,
  PRIMARY KEY (decision_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS aftermath.paper_fills (
  id text PRIMARY KEY,
  decision_id text NOT NULL REFERENCES aftermath.decisions(id),
  idempotency_key text NOT NULL UNIQUE,
  status text NOT NULL,
  cost_json jsonb NOT NULL,
  created_at_utc timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS aftermath.ledger_lines (
  seq bigserial PRIMARY KEY,
  line_hash text NOT NULL,
  prev_hash text NOT NULL,
  body jsonb NOT NULL,
  signature text NOT NULL,
  pubkey_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS aftermath.receipts (
  id text PRIMARY KEY,
  ledger_seq bigint NOT NULL REFERENCES aftermath.ledger_lines(seq),
  ots_status text NOT NULL
);

CREATE INDEX IF NOT EXISTS events_instrument_time ON aftermath.events (instrument_id, event_time_utc DESC);
CREATE INDEX IF NOT EXISTS decision_evidence_order ON aftermath.decision_evidence (decision_id, position);

CREATE OR REPLACE FUNCTION aftermath.reject_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS events_no_update ON aftermath.events;
CREATE TRIGGER events_no_update BEFORE UPDATE OR DELETE ON aftermath.events
FOR EACH ROW EXECUTE FUNCTION aftermath.reject_mutation();
DROP TRIGGER IF EXISTS evidence_no_update ON aftermath.evidence;
CREATE TRIGGER evidence_no_update BEFORE UPDATE OR DELETE ON aftermath.evidence
FOR EACH ROW EXECUTE FUNCTION aftermath.reject_mutation();
DROP TRIGGER IF EXISTS ledger_no_update ON aftermath.ledger_lines;
CREATE TRIGGER ledger_no_update BEFORE UPDATE OR DELETE ON aftermath.ledger_lines
FOR EACH ROW EXECUTE FUNCTION aftermath.reject_mutation();

ALTER TABLE aftermath.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE aftermath.evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE aftermath.decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE aftermath.decision_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE aftermath.paper_fills ENABLE ROW LEVEL SECURITY;
ALTER TABLE aftermath.ledger_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE aftermath.receipts ENABLE ROW LEVEL SECURITY;
