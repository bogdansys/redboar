import tkinter as tk
from tkinter import ttk

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    tutorial = ttk.LabelFrame(parent_frame, text="Tutorial", padding="6")
    tutorial.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,6))
    ttk.Label(
        tutorial,
        text=(
            "Nikto performs baseline web vuln scans.\n"
            "- Target: Host or URL. Format/Tuning optional; SSL forces HTTPS.\n"
            "- Disable prompts with -ask no for automation.\n"
            "Check Command → Preview, then Start."
        ),
        justify="left",
        wraplength=700,
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(parent_frame, text="Target Host/URL (-h):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.nikto_target_var = tk.StringVar()
    app_instance.nikto_target_entry = ttk.Entry(parent_frame, textvariable=app_instance.nikto_target_var, width=50)
    app_instance.nikto_target_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
    app_instance.nikto_target_entry.bind("<KeyRelease>", app_instance.update_command_preview)

    k_options_frame = ttk.LabelFrame(parent_frame, text="Options", padding="10")
    k_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

    ttk.Label(k_options_frame, text="Output Format (-Format):").grid(row=0, column=0, sticky="w", padx=5,pady=2)
    app_instance.nikto_format_var = tk.StringVar(value="txt")
    app_instance.nikto_format_combo = ttk.Combobox(k_options_frame, textvariable=app_instance.nikto_format_var,
                                           values=['txt', 'csv', 'htm', 'xml', 'nbe'], state="readonly", width=5)
    app_instance.nikto_format_combo.grid(row=0, column=1, sticky="w", padx=5,pady=2)
    app_instance.nikto_format_combo.bind("<<ComboboxSelected>>", app_instance.update_command_preview)

    ttk.Label(k_options_frame, text="Tuning (-Tuning x):").grid(row=1, column=0, sticky="w", padx=5,pady=2)
    app_instance.nikto_tuning_var = tk.StringVar(value="x 123b")
    app_instance.nikto_tuning_combo = ttk.Combobox(k_options_frame, textvariable=app_instance.nikto_tuning_var,
                                            values=['x 0123456789abcde', 'x 123b', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e'], width=15)
    app_instance.nikto_tuning_combo.grid(row=1, column=1, sticky="w", padx=5,pady=2)
    app_instance.nikto_tuning_combo.bind("<<ComboboxSelected>>", app_instance.update_command_preview)
    
    app_instance.nikto_ssl_var = tk.BooleanVar()
    ttk.Checkbutton(k_options_frame, text="-ssl (Force SSL mode)", variable=app_instance.nikto_ssl_var, command=app_instance.update_command_preview).grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app_instance.nikto_ask_no_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(k_options_frame, text="-ask no (Disable prompts)", variable=app_instance.nikto_ask_no_var, command=app_instance.update_command_preview).grid(row=2, column=1, sticky="w", padx=5, pady=2)

def build_command(app_instance):
    cmd_list = []
    target = app_instance.nikto_target_var.get().strip()
    if not target: raise ValueError("Nikto target cannot be empty.")
    cmd_list.extend(['-h', target])
    if app_instance.nikto_format_var.get(): cmd_list.extend(['-Format', app_instance.nikto_format_var.get()])
    if app_instance.nikto_tuning_var.get(): cmd_list.extend(['-Tuning', app_instance.nikto_tuning_var.get()])
    if app_instance.nikto_ssl_var.get(): cmd_list.append("-ssl")
    if app_instance.nikto_ask_no_var.get(): cmd_list.extend(["-ask", "no"])
    cmd_list.append("-Display")
    cmd_list.append("1234D")
    return cmd_list
