"""Bootstrap the Neon `pairs` table. Idempotent; safe to run repeatedly.

Usage:
    melilo-migrate
"""
from __future__ import annotations

from melilo.store import bootstrap_schema


def main() -> None:
    bootstrap_schema()
    print("schema bootstrapped: pairs table + indexes ensured")


if __name__ == "__main__":
    main()
