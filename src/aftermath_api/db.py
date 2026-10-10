"""Postgres access. Application traffic uses the transaction pooler URL. Migrations use DIRECT_URL."""

from __future__ import annotations

import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def migration_paths() -> list[Path]:
    candidates = [ROOT / "migrations", ROOT.parent / "migrations"]
    for directory in candidates:
        paths = sorted(directory.glob("*.sql"))
        names = {path.name for path in paths}
        if "0001_init.sql" in names and "0002_paper_runs.sql" in names:
            return paths
    raise SystemExit("migrations missing")


def apply_migration(conn, schema: str = "aftermath") -> None:
    if not schema.replace("_", "").isalnum():
        raise ValueError("schema name")
    for path in migration_paths():
        sql = path.read_text(encoding="utf-8").replace("aftermath", schema)
        conn.execute(sql)
    conn.commit()
    found = conn.execute("SELECT to_regclass(%s)", (f"{schema}.paper_runs",)).fetchone()[0]
    if found is None:
        raise SystemExit("paper_runs missing")


def connect(url: str, *, prepare: bool = True):
    import psycopg
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "pgbouncer"]
    cleaned = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    kwargs = {"connect_timeout": 10}
    if not prepare:
        kwargs["prepare_threshold"] = None
    last: Exception | None = None
    for attempt in range(3):
        try:
            return psycopg.connect(cleaned, **kwargs)
        except Exception as exc:
            last = exc
            if attempt == 2:
                raise
            time.sleep(0.2 * (attempt + 1))
    raise last if last else RuntimeError("database connect failed")
