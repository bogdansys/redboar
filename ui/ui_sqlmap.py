import tkinter as tk
from tkinter import ttk

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    tutorial = ttk.LabelFrame(parent_frame, text="Tutorial", padding="6")
    tutorial.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,6))
    ttk.Label(
        tutorial,
        text=(
            "SQLMap tests/dumps SQL injection.\n"
            "- Target URL required. Use --batch for non-interactive.\n"
            "- Enumeration: choose dbs/tables/dump and optionally DB/Table names.\n"
            "- Tuning: Level/Risk control depth and noise.\n"
            "Review Command → Preview, then Start."
        ),
        justify="left",
        wraplength=700,
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(parent_frame, text="Target URL (-u):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.sqlmap_target_var = tk.StringVar()
    app_instance.sqlmap_target_entry = ttk.Entry(parent_frame, textvariable=app_instance.sqlmap_target_var, width=50)
    app_instance.sqlmap_target_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
    app_instance.sqlmap_target_entry.bind("<KeyRelease>", app_instance.update_command_preview)

    s_options_frame = ttk.LabelFrame(parent_frame, text="Options", padding="10")
    s_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

    app_instance.sqlmap_batch_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(s_options_frame, text="--batch (Non-interactive)", variable=app_instance.sqlmap_batch_var, command=app_instance.update_command_preview).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)
    
    s_enum_frame = ttk.LabelFrame(s_options_frame, text="Enumeration", padding="5")
    s_enum_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

    app_instance.sqlmap_dbs_var = tk.BooleanVar()
    ttk.Checkbutton(s_enum_frame, text="--dbs (Databases)", variable=app_instance.sqlmap_dbs_var, command=app_instance.update_command_preview).grid(row=0, column=0, sticky="w", padx=5, pady=2)
    app_instance.sqlmap_current_db_var = tk.BooleanVar()
    ttk.Checkbutton(s_enum_frame, text="--current-db (Current DB)", variable=app_instance.sqlmap_current_db_var, command=app_instance.update_command_preview).grid(row=0, column=1, sticky="w", padx=5, pady=2)
    app_instance.sqlmap_tables_var = tk.BooleanVar()
    ttk.Checkbutton(s_enum_frame, text="--tables (Tables)", variable=app_instance.sqlmap_tables_var, command=app_instance.update_command_preview).grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.sqlmap_dump_var = tk.BooleanVar()
    ttk.Checkbutton(s_enum_frame, text="--dump (Dump Data)", variable=app_instance.sqlmap_dump_var, command=app_instance.update_command_preview).grid(row=1, column=1, sticky="w", padx=5, pady=2)

    ttk.Label(s_enum_frame, text="DB (-D):").grid(row=2, column=0, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_db_name_var = tk.StringVar()
    ttk.Entry(s_enum_frame, textvariable=app_instance.sqlmap_db_name_var, width=15).grid(row=2, column=1, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_db_name_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())

    ttk.Label(s_enum_frame, text="Table (-T):").grid(row=3, column=0, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_table_name_var = tk.StringVar()
    ttk.Entry(s_enum_frame, textvariable=app_instance.sqlmap_table_name_var, width=15).grid(row=3, column=1, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_table_name_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())
    
    s_tuning_frame = ttk.LabelFrame(s_options_frame, text="Tuning", padding="5")
    s_tuning_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

    ttk.Label(s_tuning_frame, text="Level (1-5):").grid(row=0, column=0, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_level_var = tk.StringVar(value="1")
    ttk.Entry(s_tuning_frame, textvariable=app_instance.sqlmap_level_var, width=3).grid(row=0, column=1, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_level_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())

    ttk.Label(s_tuning_frame, text="Risk (0-3):").grid(row=1, column=0, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_risk_var = tk.StringVar(value="1")
    ttk.Entry(s_tuning_frame, textvariable=app_instance.sqlmap_risk_var, width=3).grid(row=1, column=1, sticky="w", padx=5,pady=2)
    app_instance.sqlmap_risk_var.trace_add("write", lambda *args, app=app_instance: app.update_command_preview())

def build_command(app_instance):
    cmd_list = []
    target = app_instance.sqlmap_target_var.get().strip()
    if not target: raise ValueError("SQLMap target URL cannot be empty.")
    cmd_list.extend(['-u', target])
    if app_instance.sqlmap_batch_var.get(): cmd_list.append("--batch")
    if app_instance.sqlmap_dbs_var.get(): cmd_list.append("--dbs")
    if app_instance.sqlmap_current_db_var.get(): cmd_list.append("--current-db")
    
    db_name = app_instance.sqlmap_db_name_var.get().strip()
    table_name = app_instance.sqlmap_table_name_var.get().strip()

    if app_instance.sqlmap_tables_var.get():
        cmd_list.append("--tables")
        if db_name: cmd_list.extend(['-D', db_name])
    
    if app_instance.sqlmap_dump_var.get():
        cmd_list.append("--dump")
        if db_name: cmd_list.extend(['-D', db_name])
        if table_name: cmd_list.extend(['-T', table_name])
    elif db_name and not app_instance.sqlmap_tables_var.get() and not app_instance.sqlmap_dump_var.get():
            cmd_list.extend(['-D', db_name])

    if app_instance.sqlmap_level_var.get(): cmd_list.extend(["--level", app_instance.sqlmap_level_var.get().strip()])
    if app_instance.sqlmap_risk_var.get(): cmd_list.extend(["--risk", app_instance.sqlmap_risk_var.get().strip()])
    cmd_list.append("--disable-coloring")
    return cmd_list
