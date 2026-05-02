"""Daemon server entrypoint."""

from __future__ import annotations

import uvicorn


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    uvicorn.run("sage.api.app:app", host=host, port=port)
