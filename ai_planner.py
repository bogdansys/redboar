#!/usr/bin/env python3
from typing import List, Dict, Any
import json
import logging

import ai_client
import ai_schemas
import ai_redaction

logger = logging.getLogger("redboar")


def _build_system_prompt() -> str:
    return (
        "You are a penetration testing assistant operating on Linux. "
        "You must only suggest actions using a small set of known tools with restricted parameters. "
        "NEVER suggest arbitrary shell commands. Respect scope constraints strictly."
    )


def _build_planning_prompt(goal: str, scope: Dict[str, Any], context_summary: str) -> str:
    schemas = ai_schemas.get_tool_schemas()
    prompt = {
        "goal": goal,
        "scope": scope,
        "recent_findings": ai_redaction.redact(context_summary or ""),
        "available_tools": schemas,
        "instructions": (
            "Return a JSON array of steps. Each step is either: "
            "{\"tool\": <DisplayName>, \"params\": {...}, \"why\": <rationale>} "
            "or {\"action\": \"summarize\", \"why\": <rationale>}. "
            "Only use tool names exactly as listed in available_tools."
        ),
    }
    return json.dumps(prompt, indent=2)


def plan_steps(goal: str, scope: Dict[str, Any], context_summary: str = "", max_tokens: int = 1200) -> List[Dict[str, Any]]:
    """Ask the AI to propose a plan of structured steps.

    Returns a list of dicts. The caller must validate against schemas before use.
    """
    sys_msg = _build_system_prompt()
    user_msg = _build_planning_prompt(goal, scope, context_summary)
    raw = ai_client.chat_completion(user_msg, system=sys_msg, max_tokens=max_tokens)
    try:
        # Attempt to parse the first JSON array in the text
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end+1])
        # Fallback if the entire content is JSON
        return json.loads(raw)
    except Exception as e:
        logger.debug("Planner parse error: %s; content=%r", e, raw[:500])
        raise


