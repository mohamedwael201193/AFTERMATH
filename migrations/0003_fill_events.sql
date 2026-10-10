-- Forward-only. Append-only fill lifecycle. Does not change existing fill rows.
CREATE TABLE IF NOT EXISTS aftermath.fill_events (
  seq bigserial PRIMARY KEY,
  fill_id text NOT NULL,
  status text NOT NULL,
  cost_json jsonb NOT NULL,
  recorded_at_utc timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fill_events_fill ON aftermath.fill_events (fill_id, seq);

DROP TRIGGER IF EXISTS fill_events_no_update ON aftermath.fill_events;
CREATE TRIGGER fill_events_no_update BEFORE UPDATE OR DELETE ON aftermath.fill_events
FOR EACH ROW EXECUTE FUNCTION aftermath.reject_mutation();
