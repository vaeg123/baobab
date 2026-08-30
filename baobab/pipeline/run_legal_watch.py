"""Exécute manuellement un cycle du moteur de veille Baobab."""

from __future__ import annotations

import asyncio
import json

from baobab.watch_engine import run_watch_cycle


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_watch_cycle(trigger="manual_pipeline")), ensure_ascii=False, indent=2))
