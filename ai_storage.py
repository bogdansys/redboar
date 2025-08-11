#!/usr/bin/env python3
import json
import datetime as _dt
from pathlib import Path
from typing import Any, Dict


CONFIG_DIR = Path.home() / ".config" / "redboar"
AI_RUNS = CONFIG_DIR / "ai_runs.jsonl"


def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def log_event(event: Dict[str, Any]) -> None:
    ensure_dirs()
    event = dict(event)
    if "timestamp" not in event:
        event["timestamp"] = _dt.datetime.now().isoformat()
    with AI_RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


