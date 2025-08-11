import tkinter as tk
from tkinter import ttk

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    # Tutorial
    tutorial = ttk.LabelFrame(parent_frame, text="Tutorial", padding="6")
    tutorial.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,6))
    ttk.Label(
        tutorial,
        text=(
            "Gobuster is a content discovery tool.\n"
            "- Mode: dir (URLs), dns (subdomains), vhost (virtual hosts).\n"
            "- Target: dir/vhost require http(s) URL; dns requires a domain.\n"
            "- Wordlist: required. Threads, extensions, and status filters are optional.\n"
            "Use Command → Preview to verify, then Start. Stop anytime; export output if needed."
        ),
        justify="left",
        wraplength=700,
    ).grid(row=0, column=0, sticky="w")
    
    ttk.Label(parent_frame, text="Mode:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.gobuster_modes = {'Directory/File': 'dir', 'DNS Subdomain': 'dns', 'Virtual Host': 'vhost'}
    app_instance.gobuster_current_mode_var = tk.StringVar(value='Directory/File')
    app_instance.gobuster_mode_combo = ttk.Combobox(parent_frame, textvariable=app_instance.gobuster_current_mode_var,
                                            values=list(app_instance.gobuster_modes.keys()), state="readonly", width=15)
    app_instance.gobuster_mode_combo.grid(row=1, column=1, sticky="w", padx=5, pady=2)
    app_instance.gobuster_mode_combo.bind("<<ComboboxSelected>>", app_instance.update_command_preview)

    ttk.Label(parent_frame, text="Target URL/Domain:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app_instance.gobuster_target_var = tk.StringVar()
    app_instance.gobuster_target_entry = ttk.Entry(parent_frame, textvariable=app_instance.gobuster_target_var, width=50)
    app_instance.gobuster_target_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
    app_instance.gobuster_target_entry.bind("<KeyRelease>", app_instance.update_command_preview)

    ttk.Label(parent_frame, text="Wordlist:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
    app_instance.gobuster_wordlist_var = tk.StringVar()
    app_instance.gobuster_wordlist_entry = ttk.Entry(parent_frame, textvariable=app_instance.gobuster_wordlist_var, width=50)
    app_instance.gobuster_wordlist_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
    app_instance.gobuster_wordlist_entry.bind("<KeyRelease>", app_instance.update_command_preview)
    app_instance.gobuster_browse_button = ttk.Button(parent_frame, text="Browse...",
                                             command=lambda: app_instance.browse_file(app_instance.gobuster_wordlist_var))
    app_instance.gobuster_browse_button.grid(row=3, column=2, sticky="e", padx=5, pady=2)

    g_options_frame = ttk.LabelFrame(parent_frame, text="Options", padding="10")
    g_options_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

    app_instance.gobuster_threads_var = tk.StringVar(value='10')
    ttk.Label(g_options_frame, text="Threads (-t):").grid(row=0, column=0, sticky="w", padx=5,pady=2)
    ttk.Entry(g_options_frame, textvariable=app_instance.gobuster_threads_var, width=5).grid(row=0, column=1, sticky="w", padx=5,pady=2)

    app_instance.gobuster_extensions_var = tk.StringVar()
    ttk.Label(g_options_frame, text="Extensions (-x):").grid(row=1, column=0, sticky="w", padx=5,pady=2)
    ttk.Entry(g_options_frame, textvariable=app_instance.gobuster_extensions_var, width=20).grid(row=1, column=1, sticky="w", padx=5,pady=2)
    ttk.Label(g_options_frame, text="(e.g. php,txt,html)").grid(row=1, column=2, sticky="w", padx=5,pady=2)

    app_instance.gobuster_status_codes_var = tk.StringVar(value='200,204,301,302,307,401,403')
    ttk.Label(g_options_frame, text="Include Codes (-s):").grid(row=2, column=0, sticky="w", padx=5,pady=2)
    ttk.Entry(g_options_frame, textvariable=app_instance.gobuster_status_codes_var, width=30).grid(row=2, column=1, columnspan=2, sticky="ew", padx=5,pady=2)

    for var in [app_instance.gobuster_threads_var, app_instance.gobuster_extensions_var, app_instance.gobuster_status_codes_var]:
        var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())


import os


def build_command(app_instance):
    cmd_list = []
    mode_cmd = app_instance.gobuster_modes.get(app_instance.gobuster_current_mode_var.get())
    target = app_instance.gobuster_target_var.get().strip()
    wordlist = app_instance.gobuster_wordlist_var.get().strip()

    if not mode_cmd:
        raise ValueError("Invalid Gobuster mode.")
    if not target:
        raise ValueError("Gobuster target cannot be empty.")
    if not wordlist:
        raise ValueError("Gobuster wordlist cannot be empty.")
    if not os.path.exists(wordlist):
        raise ValueError(f"Gobuster wordlist not found: {wordlist}")

    cmd_list.append(mode_cmd)
    if mode_cmd in ['dir', 'vhost']:
        if not target.startswith(('http://', 'https://')):
            raise ValueError("Gobuster dir/vhost target must start with http:// or https://")
        cmd_list.extend(['-u', target])
    elif mode_cmd == 'dns':
        if target.startswith(('http://', 'https://')):
            raise ValueError("Gobuster DNS target should be a domain (e.g., example.com).")
        cmd_list.extend(['-d', target])

    cmd_list.extend(['-w', wordlist])
    if app_instance.gobuster_threads_var.get():
        cmd_list.extend(['-t', app_instance.gobuster_threads_var.get().strip()])
    if app_instance.gobuster_extensions_var.get():
        cmd_list.extend(['-x', app_instance.gobuster_extensions_var.get().strip()])
    if app_instance.gobuster_status_codes_var.get():
        cmd_list.extend(['-s', app_instance.gobuster_status_codes_var.get().strip()])
    cmd_list.append('--no-progress')
    cmd_list.append('-q')
    return cmd_list