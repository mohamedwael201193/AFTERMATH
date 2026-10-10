"""Three bearers. Comparison is constant-time. Reader cannot decide or run jobs."""

from __future__ import annotations

import hmac

from .config import Settings
from .errors import ApiError


def _eq(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode(), b.encode())


def bearer(header: str | None) -> str:
    if not header or not header.lower().startswith("bearer "):
        raise ApiError("UNAUTHORIZED", "missing bearer", 401)
    return header.split(" ", 1)[1].strip()


def require_reader(settings: Settings, header: str | None) -> None:
    token = bearer(header)
    if _eq(token, settings.decision_token) or _eq(token, settings.job_token):
        raise ApiError("FORBIDDEN", "reader token required", 403)
    if not _eq(token, settings.reader_token):
        raise ApiError("UNAUTHORIZED", "reader token required", 401)


def require_decision(settings: Settings, header: str | None) -> None:
    token = bearer(header)
    if _eq(token, settings.reader_token) or _eq(token, settings.job_token):
        raise ApiError("FORBIDDEN", "decision token required", 403)
    if not _eq(token, settings.decision_token):
        raise ApiError("UNAUTHORIZED", "decision token required", 401)


def require_job(settings: Settings, header: str | None) -> None:
    token = bearer(header)
    if _eq(token, settings.reader_token) or _eq(token, settings.decision_token):
        raise ApiError("FORBIDDEN", "job token required", 403)
    if not _eq(token, settings.job_token):
        raise ApiError("UNAUTHORIZED", "job token required", 401)
