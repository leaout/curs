# coding: utf-8
"""ASGI and command-line entry point for Curs Trading V2."""

import uvicorn

from trading_v2.api import create_app
from trading_v2.config import get_settings

app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "trading_v2.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    main()
