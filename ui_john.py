import tkinter as tk
from tkinter import ttk
import os

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)
    ttk.Label(parent_frame, text="Hash File:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.john_hash_file_var = tk.StringVar()
    app_instance.john_hash_file_entry = ttk.Entry(parent_frame, textvariable=app_instance.john_hash_file_var, width=40)
    app_instance.john_hash_file_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
    app_instance.john_hash_file_entry.bind("<KeyRelease>", app_instance.update_command_preview)
    app_instance.john_browse_hash_button = ttk.Button(parent_frame, text="Browse...",
                                              command=lambda: app_instance.browse_file(app_instance.john_hash_file_var, "Select Hash File"))
    app_instance.john_browse_hash_button.grid(row=1, column=2, sticky="e", padx=5, pady=2)

    j_options_frame = ttk.LabelFrame(parent_frame, text="Options", padding="10")
    j_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

    ttk.Label(j_options_frame, text="Wordlist (Optional):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    app_instance.john_wordlist_var = tk.StringVar()
    app_instance.john_wordlist_entry = ttk.Entry(j_options_frame, textvariable=app_instance.john_wordlist_var, width=30)
    app_instance.john_wordlist_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
    app_instance.john_browse_wordlist_button = ttk.Button(j_options_frame, text="Browse...",
                                                  command=lambda: app_instance.browse_file(app_instance.john_wordlist_var, "Select Wordlist"))
    app_instance.john_browse_wordlist_button.grid(row=0, column=2, sticky="e", padx=5, pady=2)
    app_instance.john_wordlist_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())

    ttk.Label(j_options_frame, text="Format (Optional):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.john_format_var = tk.StringVar()
    ttk.Entry(j_options_frame, textvariable=app_instance.john_format_var, width=15).grid(row=1, column=1, sticky="w", padx=5, pady=2)
    app_instance.john_format_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())

    ttk.Label(j_options_frame, text="Session Name (Optional):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app_instance.john_session_var = tk.StringVar()
    ttk.Entry(j_options_frame, textvariable=app_instance.john_session_var, width=15).grid(row=2, column=1, sticky="w", padx=5, pady=2)
    app_instance.john_session_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())
    
    app_instance.john_show_cracked_var = tk.BooleanVar()
    ttk.Checkbutton(j_options_frame, text="--show (Show cracked for session)", variable=app_instance.john_show_cracked_var, command=app_instance.update_command_preview).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=2)

def build_command(app_instance):
    cmd_list = []
    hash_file = app_instance.john_hash_file_var.get().strip()
    if not hash_file: raise ValueError("John hash file cannot be empty.")
    if not os.path.exists(hash_file) and not app_instance.john_show_cracked_var.get(): # Show command can run on non-existent if session exists
        raise ValueError(f"John hash file not found: {hash_file}")
    
    if app_instance.john_show_cracked_var.get():
        cmd_list.append("--show")
        if app_instance.john_format_var.get(): cmd_list.append(f"--format={app_instance.john_format_var.get().strip()}")
        cmd_list.append(hash_file) 
        if app_instance.john_session_var.get(): cmd_list.append(f"--session={app_instance.john_session_var.get().strip()}")
    else:
        cmd_list.append(hash_file)
        if app_instance.john_wordlist_var.get():
            wordlist = app_instance.john_wordlist_var.get().strip()
            if not os.path.exists(wordlist): raise ValueError(f"John wordlist not found: {wordlist}")
            cmd_list.append(f"--wordlist={wordlist}")
        if app_instance.john_format_var.get(): cmd_list.append(f"--format={app_instance.john_format_var.get().strip()}")
        if app_instance.john_session_var.get(): cmd_list.append(f"--session={app_instance.john_session_var.get().strip()}")
    return cmd_list
