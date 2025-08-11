#!/usr/bin/env python3
import os
import json
import time
import logging
from typing import Optional
from urllib import request, error

logger = logging.getLogger("redboar")


OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
DEFAULT_MODEL = os.environ.get("REDBOAR_OPENAI_MODEL", "gpt-4o-mini")


def is_configured() -> bool:
    return bool(os.environ.get("REDBOAR_OPENAI_API_KEY"))


def chat_completion(prompt: str, system: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 800) -> str:
    """Minimal OpenAI Chat Completions client with retries.

    Returns the assistant message content as a string.
    Raises RuntimeError on failures.
    """
    api_key = os.environ.get("REDBOAR_OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key not configured. Set REDBOAR_OPENAI_API_KEY.")

    model = model or DEFAULT_MODEL
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }

    payload = json.dumps(data).encode("utf-8")

    last_err = None
    for attempt in range(3):
        try:
            req = request.Request(url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                parsed = json.loads(body.decode("utf-8"))
                content = parsed["choices"][0]["message"]["content"]
                return content or ""
        except error.HTTPError as e:
            last_err = e
            logger.debug("OpenAI HTTPError %s: %s", e.code, e.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            last_err = e
            logger.debug("OpenAI request error: %s", e)
        time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"OpenAI request failed: {last_err}")


