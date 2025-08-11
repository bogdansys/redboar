#!/usr/bin/env python3
import re

_PATTERNS = [
    re.compile(r"(Bearer\s+[A-Za-z0-9\-\._~\+/]+=*)"),
    re.compile(r"(Authorization:\s*\S+)"),
    re.compile(r"(api[_-]?key\s*[:=]\s*\S+)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*\S+)", re.IGNORECASE),
    re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
]


def redact(text: str) -> str:
    redacted = text
    for pat in _PATTERNS:
        redacted = pat.sub("[REDACTED]", redacted)
    return redacted


