#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
from typing import Any, Dict, List

import ai_client
import ai_planner
import ai_schemas
import ai_storage
import os

logger = logging.getLogger("redboar")


def create_ai_tab(parent_frame, app):
    parent_frame.columnconfigure(1, weight=1)
    row = 0

    # API key controls at the very top (clear and visible)
    api_frame = ttk.LabelFrame(parent_frame, text="OpenAI API", padding=8)
    api_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=(5,5))
    api_frame.columnconfigure(1, weight=1)
    ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky="w")
    app.ai_api_key_var = tk.StringVar(value=os.environ.get("REDBOAR_OPENAI_API_KEY", ""))
    key_entry = ttk.Entry(api_frame, textvariable=app.ai_api_key_var, show='*', width=60)
    key_entry.grid(row=0, column=1, sticky="ew", padx=(6,6))
    def _toggle_key_visibility():
        key_entry.config(show='' if key_entry.cget('show') == '*' else '*')
    ttk.Button(api_frame, text="Show/Hide", command=_toggle_key_visibility).grid(row=0, column=2, padx=(0,6))
    ttk.Button(api_frame, text="Save", command=lambda: _save_api_key(app)).grid(row=0, column=3)
    row += 1

    ttk.Label(parent_frame, text="Goal:").grid(row=row, column=0, sticky="w")
    app.ai_goal_var = tk.StringVar()
    ttk.Entry(parent_frame, textvariable=app.ai_goal_var, width=80).grid(row=row, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
    row += 1

    scope_frame = ttk.LabelFrame(parent_frame, text="Scope & Limits", padding=10)
    scope_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    scope_frame.columnconfigure(1, weight=1)
    row += 1

    ttk.Label(scope_frame, text="Targets (comma or CIDR):").grid(row=0, column=0, sticky="w")
    app.ai_scope_targets_var = tk.StringVar()
    ttk.Entry(scope_frame, textvariable=app.ai_scope_targets_var, width=60).grid(row=0, column=1, sticky="ew", padx=5, pady=2)

    ttk.Label(scope_frame, text="Time budget (mins):").grid(row=1, column=0, sticky="w")
    app.ai_time_budget_var = tk.StringVar(value="30")
    ttk.Entry(scope_frame, textvariable=app.ai_time_budget_var, width=6).grid(row=1, column=1, sticky="w", padx=5, pady=2)

    app.ai_mode_auto_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(scope_frame, text="Auto-run within constraints (experimental)", variable=app.ai_mode_auto_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(5,0))

    ttk.Label(scope_frame, text="Engine:").grid(row=3, column=0, sticky="w", pady=(5,0))
    app.ai_engine_var = tk.StringVar(value=("ChatGPT" if ai_client.is_configured() else "Local"))
    ttk.Combobox(scope_frame, textvariable=app.ai_engine_var, values=["Local", "ChatGPT"], state="readonly", width=10).grid(row=3, column=1, sticky="w", padx=5, pady=(5,0))

    controls = ttk.Frame(parent_frame)
    controls.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    row += 1

    ttk.Button(controls, text="Plan Steps", command=lambda: _plan(app)).grid(row=0, column=0, padx=5)
    ttk.Button(controls, text="Run Selected", command=lambda: _run_selected(app)).grid(row=0, column=1, padx=5)

    app.ai_plan = ttk.Treeview(parent_frame, columns=("tool", "params", "why"), show="headings", height=10)
    app.ai_plan.heading("tool", text="Tool/Action")
    app.ai_plan.heading("params", text="Params")
    app.ai_plan.heading("why", text="Rationale")
    app.ai_plan.column("tool", width=160)
    app.ai_plan.column("params", width=400)
    app.ai_plan.column("why", width=300)
    app.ai_plan.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
    parent_frame.rowconfigure(row, weight=1)
    row += 1

    info_text = (
        "Engine: Local works offline. ChatGPT requires REDBOAR_OPENAI_API_KEY. "
        "All suggestions respect scope constraints and require your approval."
    )
    info = ttk.Label(parent_frame, text=info_text, foreground="grey")
    info.grid(row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(0,5))


def _plan(app):
    goal = app.ai_goal_var.get().strip()
    if not goal:
        messagebox.showwarning("AI", "Enter a goal to plan steps.")
        return
    scope = {
        "targets": app.ai_scope_targets_var.get().strip(),
        "time_budget_min": app.ai_time_budget_var.get().strip(),
    }
    try:
        engine = app.ai_engine_var.get()
        if engine == "ChatGPT":
            if not ai_client.is_configured():
                # fallback to Local if key missing
                engine = "Local"
            else:
                steps = ai_planner.plan_steps(goal, scope)
        if engine == "Local":
            steps = _local_plan(goal, scope)
    except Exception as e:
        messagebox.showerror("AI", f"Planning failed: {e}")
        return
    # Render
    for item in app.ai_plan.get_children():
        app.ai_plan.delete(item)
    for i, step in enumerate(steps):
        if "tool" in step:
            tool = step.get("tool")
            params = json.dumps(step.get("params", {}))
            why = step.get("why", "")
            app.ai_plan.insert("", "end", iid=str(i), values=(tool, params, why))
        else:
            action = step.get("action", "summarize")
            why = step.get("why", "")
            app.ai_plan.insert("", "end", iid=str(i), values=(action, "{}", why))
    ai_storage.log_event({"type": "plan", "goal": goal, "scope": scope, "steps": steps})


def _run_selected(app):
    sel = app.ai_plan.selection()
    if not sel:
        messagebox.showinfo("AI", "Select at least one step to run.")
        return
    # Convert a selected tool call to the corresponding tab + set fields where possible
    for item in sel:
        tool, params_json, _why = app.ai_plan.item(item, "values")
        if tool in app.tool_frames:
            # Switch tab
            idx = list(app.tool_frames.keys()).index(tool)
            app.main_notebook.select(idx)
        else:
            # Non-tool action like summarize; skip for now
            continue
        # Best-effort: parse params and set common fields
        try:
            params = json.loads(params_json)
        except Exception:
            params = {}

        # Minimal field mapping examples (non-destructive, best-effort)
        if tool == "Nmap":
            if "targets" in params:
                app.nmap_target_var.set(params.get("targets", ""))
            if "ports" in params:
                app.nmap_ports_var.set(params.get("ports", ""))
        elif tool == "Gobuster":
            if "target" in params:
                app.gobuster_target_var.set(params.get("target", ""))
            if "wordlist" in params:
                app.gobuster_wordlist_var.set(params.get("wordlist", ""))
        elif tool == "SQLMap":
            if "url" in params:
                app.sqlmap_target_var.set(params.get("url", ""))
        elif tool == "Nikto":
            if "target" in params:
                app.nikto_target_var.set(params.get("target", ""))
        elif tool == "John the Ripper":
            if "hash_file" in params:
                app.john_hash_file_var.set(params.get("hash_file", ""))

        app.update_command_preview()
    messagebox.showinfo("AI", "Selected steps applied to tool tabs. Review and Start when ready.")


def _save_api_key(app):
    key = app.ai_api_key_var.get().strip()
    if not key:
        # Clear from env and state
        os.environ.pop("REDBOAR_OPENAI_API_KEY", None)
        # Update engine to Local
        app.ai_engine_var.set("Local")
        messagebox.showinfo("AI", "API key cleared. Engine set to Local.")
        return
    os.environ["REDBOAR_OPENAI_API_KEY"] = key
    # Persist in app state if available
    try:
        # Use existing state persistence
        state = app._collect_state(include_current_tool=False)
        state.setdefault("ai", {})
        state["ai"]["api_key_set"] = True
        # Do not store the actual key by default for safety; set a flag only.
        # If you want to persist the key (less secure), uncomment the next line:
        # state["ai"]["api_key"] = key
        app._ensure_config_dir()
        with app._state_path.open('w', encoding='utf-8') as f:
            import json
            json.dump(state, f, indent=2)
    except Exception:
        pass
    # Update engine to ChatGPT
    app.ai_engine_var.set("ChatGPT")
    messagebox.showinfo("AI", "API key saved for this session. Engine set to ChatGPT.")


def _local_plan(goal: str, scope: dict) -> list:
    """Offline heuristic plan based on goal keywords and provided scope.
    Produces a list of structured steps similar to the ChatGPT planner.
    """
    targets = scope.get("targets", "").strip()
    plan = []
    lower = goal.lower()
    # Always start with discovery if targets given
    if targets:
        plan.append({
            "tool": "Nmap",
            "params": {
                "targets": targets,
                "ports": "",
                "scan_types": {"-sS (TCP SYN)": True},
                "ping_scan": False,
                "no_ping": True,
                "os_detect": True,
                "version_detect": True,
                "fast": False,
                "verbose": True
            },
            "why": "Initial discovery and service/version detection"
        })
    if any(k in lower for k in ["web", "http", "site", "dir", "vhost", "dns"]):
        plan.append({
            "tool": "Gobuster",
            "params": {
                "mode": "dir",
                "target": f"http://{targets}" if targets and not targets.startswith("http") else targets,
                "wordlist": "",
                "threads": "10",
                "extensions": "",
                "status_codes": "200,204,301,302,307,401,403"
            },
            "why": "Directory enumeration to discover hidden paths"
        })
        plan.append({
            "tool": "Nikto",
            "params": {
                "target": f"http://{targets}" if targets and not targets.startswith("http") else targets,
                "format": "txt",
                "tuning": "x 123b",
                "ssl": False,
                "ask_no": True
            },
            "why": "Baseline web vulnerability scan"
        })
    if any(k in lower for k in ["sql", "sqli", "database"]):
        plan.append({
            "tool": "SQLMap",
            "params": {
                "url": f"http://{targets}" if targets and not targets.startswith("http") else targets,
                "batch": True,
                "dbs": False,
                "current_db": False,
                "tables": False,
                "dump": False,
                "db_name": "",
                "table_name": "",
                "level": "1",
                "risk": "1"
            },
            "why": "Check for SQL injection"
        })
    if any(k in lower for k in ["hash", "john", "password"]):
        plan.append({
            "tool": "John the Ripper",
            "params": {
                "hash_file": "",
                "wordlist": "",
                "format": "",
                "session": "",
                "show": False
            },
            "why": "Attempt password cracking if hashes are available"
        })
    if not plan:
        plan.append({"action": "summarize", "why": "No clear tool mapping from goal; summarize any findings after initial discovery."})
    return plan


