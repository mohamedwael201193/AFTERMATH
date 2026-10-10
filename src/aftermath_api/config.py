"""Load production settings. Prints names and SET/MISSING only."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = ROOT / ".env"
SECRET_RE = re.compile(r"(rnd_|vcp_|ghp_|postgresql://|k1)")


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    direct_url: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_configured: bool
    reader_token: str
    decision_token: str
    job_token: str
    signing_key_path: str
    sec_user_agent: str
    web_origin: str
    decisions: str

    def public_status(self) -> dict[str, str]:
        return {
            "env": self.env,
            "database": "SET" if self.database_url else "MISSING",
            "llm": "configured" if self.llm_configured else "absent",
            "decisions": self.decisions,
            "reader_token": "SET" if self.reader_token else "MISSING",
            "decision_token": "SET" if self.decision_token else "MISSING",
            "job_token": "SET" if self.job_token else "MISSING",
            "signing_key": "SET" if self.signing_key_path else "MISSING",
            "sec_user_agent": "SET" if self.sec_user_agent else "MISSING",
        }


def load_settings(env_file: Path | None = None, environ: dict[str, str] | None = None) -> Settings:
    process = dict(os.environ if environ is None else environ)
    file_vals = _parse_env_file(env_file or Path(process.get("AFTERMATH_ENV_FILE", str(DEFAULT_ENV))))
    merged = {**file_vals, **{k: v for k, v in process.items() if v != ""}}
    if not merged.get("T2_LLM_API_KEY") and merged.get("LLM_API_KEY"):
        merged["T2_LLM_API_KEY"] = merged["LLM_API_KEY"]
    if not merged.get("T2_LLM_BASE_URL") and merged.get("LLM_BASE_URL"):
        merged["T2_LLM_BASE_URL"] = merged["LLM_BASE_URL"]
    if not merged.get("T2_LLM_MODEL") and merged.get("LLM_MODEL"):
        merged["T2_LLM_MODEL"] = merged["LLM_MODEL"]
    env = merged.get("AFTERMATH_ENV", "dev")
    db = merged.get("DATABASE_URL", "")
    if env == "prod" and not db:
        raise SystemExit(2)
    llm = merged.get("T2_LLM_API_KEY", "")
    return Settings(
        env=env,
        database_url=db,
        direct_url=merged.get("DIRECT_URL", ""),
        llm_api_key=llm,
        llm_base_url=merged.get("T2_LLM_BASE_URL", ""),
        llm_model=merged.get("T2_LLM_MODEL", ""),
        llm_configured=bool(llm and merged.get("T2_LLM_BASE_URL") and merged.get("T2_LLM_MODEL")),
        reader_token=merged.get("AFTERMATH_API_TOKEN", ""),
        decision_token=merged.get("AFTERMATH_DECISION_TOKEN", ""),
        job_token=merged.get("AFTERMATH_JOB_TOKEN", ""),
        signing_key_path=merged.get("T2_SIGNING_KEY", ""),
        sec_user_agent=merged.get("T2_SEC_USER_AGENT", ""),
        web_origin=merged.get("AFTERMATH_WEB_ORIGIN", ""),
        decisions="model" if llm else "abstain_only",
    )


def format_status(settings: Settings) -> str:
    lines = [f"{k} {v}" for k, v in settings.public_status().items()]
    text = "\n".join(lines)
    if SECRET_RE.search(text):
        raise RuntimeError("status leaked a secret pattern")
    return text
