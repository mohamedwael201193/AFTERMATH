"""Apply migrations with DIRECT_URL. Prints only the schema name and table count."""

from __future__ import annotations

import os
from pathlib import Path

from .config import ROOT
from .db import apply_migration, connect


def main() -> None:
    url = os.environ.get("DIRECT_URL", "")
    if not url:
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("DIRECT_URL="):
                url = line.split("=", 1)[1].strip()
    if not url:
        raise SystemExit("DIRECT_URL MISSING")
    schema = os.environ.get("AFTERMATH_SCHEMA", "aftermath")
    conn = connect(url)
    try:
        apply_migration(conn, schema)
        count = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = %s",
            (schema,),
        ).fetchone()[0]
    finally:
        conn.close()
    print(f"schema {schema} tables {count}")


if __name__ == "__main__":
    main()
