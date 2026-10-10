import os

import uvicorn

from .app import create_app
from .config import format_status, load_settings


def listen_port() -> int:
    return int(os.environ.get("PORT", "8000"))


def main() -> None:
    settings = load_settings()
    print(format_status(settings))
    uvicorn.run(create_app(settings), host="0.0.0.0", port=listen_port())


if __name__ == "__main__":
    main()
