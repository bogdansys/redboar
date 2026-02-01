import tkinter as tk
from tkinter import ttk
import shlex

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    info_frame = ttk.LabelFrame(parent_frame, text="SearchSploit (ExploitDB)", padding="6")
    info_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,6))
    ttk.Label(
        info_frame,
        text="Search for exploits in the local ExploitDB archive.\nEnter keywords (e.g., 'Apache 2.4', 'Windows SMB').",
        justify="left",
    ).pack(fill="x")

    # Search Term
    ttk.Label(parent_frame, text="Search Terms:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.searchsploit_var = tk.StringVar()
    entry = ttk.Entry(parent_frame, textvariable=app_instance.searchsploit_var, width=50)
    entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
    entry.bind("<KeyRelease>", app_instance.update_command_preview)

    # Options
    opts = ttk.Frame(parent_frame)
    opts.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
    
    app_instance.searchsploit_strict_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(opts, text="Strict Search (--strict)", variable=app_instance.searchsploit_strict_var,
                    command=app_instance.update_command_preview).pack(side="left", padx=5)

    app_instance.searchsploit_path_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(opts, text="Show Path (-p)", variable=app_instance.searchsploit_path_var,
                    command=app_instance.update_command_preview).pack(side="left", padx=5)

def build_command(app_instance):
    cmd_list = ["searchsploit"]
    
    terms = app_instance.searchsploit_var.get().strip()
    if not terms:
        raise ValueError("Search terms are required.")
    
    if app_instance.searchsploit_strict_var.get():
        cmd_list.append("--strict")
        
    if app_instance.searchsploit_path_var.get():
        cmd_list.append("-p")

    # Terms go last
    cmd_list.extend(shlex.split(terms))
    
    return cmd_list
