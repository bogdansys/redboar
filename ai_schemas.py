#!/usr/bin/env python3
from typing import Dict, Any


def get_tool_schemas() -> Dict[str, Dict[str, Any]]:
    """Return whitelisted tool schemas as simple metadata for the AI planner.

    The executor maps these fields to existing build_command semantics.
    """
    return {
        "Gobuster": {
            "params": ["mode", "target", "wordlist", "threads", "extensions", "status_codes"],
        },
        "Nmap": {
            "params": ["targets", "ports", "scan_types", "ping_scan", "no_ping", "os_detect", "version_detect", "fast", "verbose"],
        },
        "SQLMap": {
            "params": ["url", "batch", "dbs", "current_db", "tables", "dump", "db_name", "table_name", "level", "risk"],
        },
        "Nikto": {
            "params": ["target", "format", "tuning", "ssl", "ask_no"],
        },
        "John the Ripper": {
            "params": ["hash_file", "wordlist", "format", "session", "show"],
        },
    }


