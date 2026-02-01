import tkinter as tk
from tkinter import ttk
import os
import shlex

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    # Tutorial / Info
    info_frame = ttk.LabelFrame(parent_frame, text="Nuclei - Fast Vulnerability Scanner", padding="6")
    info_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,6))
    ttk.Label(
        info_frame,
        text=(
            "Nuclei sends requests across targets based on templates.\n"
            "Key flags: -u (target), -t (templates), -s (severity).\n"
            "Note: Ensure 'nuclei' is in your PATH."
        ),
        justify="left",
    ).pack(fill="x")

    # Target
    ttk.Label(parent_frame, text="Target URL (-u):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.nuclei_target_var = tk.StringVar()
    app_instance.nuclei_target_entry = ttk.Entry(parent_frame, textvariable=app_instance.nuclei_target_var, width=50)
    app_instance.nuclei_target_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
    app_instance.nuclei_target_entry.bind("<KeyRelease>", app_instance.update_command_preview)

    # Options Frame
    opt_frame = ttk.LabelFrame(parent_frame, text="Scan Options", padding="10")
    opt_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    opt_frame.columnconfigure(1, weight=1)

    # Templates
    ttk.Label(opt_frame, text="Templates (-t):").grid(row=0, column=0, sticky="w")
    app_instance.nuclei_templates_var = tk.StringVar(value="") # Empty default = all or config default
    ttk.Entry(opt_frame, textvariable=app_instance.nuclei_templates_var, width=40).grid(row=0, column=1, sticky="ew", padx=5, pady=2)
    ttk.Label(opt_frame, text="(e.g. 'cves', 'vulnerabilities/generic', or path)").grid(row=0, column=2, sticky="w")
    app_instance.nuclei_templates_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())

    # Severity
    ttk.Label(opt_frame, text="Severity (-s):").grid(row=1, column=0, sticky="w")
    app_instance.nuclei_severity_var = tk.StringVar(value="")
    sev_combo = ttk.Combobox(opt_frame, textvariable=app_instance.nuclei_severity_var, 
                             values=["", "critical", "high", "medium", "low", "info", "critical,high"], state="readonly")
    sev_combo.grid(row=1, column=1, sticky="w", padx=5, pady=2)
    sev_combo.bind("<<ComboboxSelected>>", lambda e: app_instance.update_command_preview())
    
    # Ratelimits
    ttk.Label(opt_frame, text="Rate Limit (-rl):").grid(row=2, column=0, sticky="w")
    app_instance.nuclei_rate_var = tk.StringVar(value="150")
    ttk.Entry(opt_frame, textvariable=app_instance.nuclei_rate_var, width=10).grid(row=2, column=1, sticky="w", padx=5, pady=2)
    app_instance.nuclei_rate_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())

def build_command(app_instance):
    cmd_list = ["nuclei"]
    
    target = app_instance.nuclei_target_var.get().strip()
    if not target:
        raise ValueError("Nuclei Target URL is required.")
    
    cmd_list.append("-u")
    cmd_list.append(target)
    
    templates = app_instance.nuclei_templates_var.get().strip()
    if templates:
        cmd_list.append("-t")
        cmd_list.append(templates)
        
    severity = app_instance.nuclei_severity_var.get().strip()
    if severity:
        cmd_list.append("-s")
        cmd_list.append(severity)
        
    rl = app_instance.nuclei_rate_var.get().strip()
    if rl:
        cmd_list.append("-rl")
        cmd_list.append(rl)

    # No interactive mode for nuclei usually needed, but output color works
    return cmd_list
