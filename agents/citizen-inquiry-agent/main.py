"""Programmatic entrypoint for the Citizen Inquiry Agent.

Used as the AM build's run command: ``python main.py``.
"""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

# Each department instance is told apart by which env file it loads — e.g.
# ENV_FILE=.env.tax-revenue python main.py — same image, different config (PLAN.md §6).
load_dotenv(os.environ.get("ENV_FILE", ".env"))

from app import CONFIG, app  # noqa: E402  (must load env before Config.from_env() runs at import time)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=CONFIG.port)


if __name__ == "__main__":
    main()
