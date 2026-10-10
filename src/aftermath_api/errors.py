from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int, retryable: bool = False):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable


def error_body(code: str, message: str, retryable: bool = False) -> dict:
    return {"error": {"code": code, "message": message, "retryable": retryable}}


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.retryable), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "UNAUTHORIZED" if exc.status_code == 401 else "SCHEMA"
        return JSONResponse(error_body(code, str(exc.detail), False), status_code=exc.status_code)
