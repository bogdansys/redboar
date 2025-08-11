import tkinter as tk
from tkinter import ttk

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    tutorial = ttk.LabelFrame(parent_frame, text="Tutorial", padding="6")
    tutorial.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,6))
    ttk.Label(
        tutorial,
        text=(
            "Nmap scans hosts/services.\n"
            "- Targets: IP/CIDR/hostnames. Ports optional (e.g., 22,80 or 1-1000).\n"
            "- Choose scan types or Ping Scan; enable OS/service detection for detail.\n"
            "Use Command → Preview to verify, then Start."
        ),
        justify="left",
        wraplength=700,
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(parent_frame, text="Target(s):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.nmap_target_var = tk.StringVar()
    app_instance.nmap_target_entry = ttk.Entry(parent_frame, textvariable=app_instance.nmap_target_var, width=50)
    app_instance.nmap_target_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
    app_instance.nmap_target_entry.bind("<KeyRelease>", app_instance.update_command_preview)

    ttk.Label(parent_frame, text="Ports:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app_instance.nmap_ports_var = tk.StringVar()
    app_instance.nmap_ports_entry = ttk.Entry(parent_frame, textvariable=app_instance.nmap_ports_var, width=30)
    app_instance.nmap_ports_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
    app_instance.nmap_ports_entry.bind("<KeyRelease>", app_instance.update_command_preview)
    ttk.Label(parent_frame, text="(e.g. 22,80 or 1-1000 or T:21-23,U:53)").grid(row=2, column=2, sticky="w", padx=5, pady=2)

    n_options_frame = ttk.LabelFrame(parent_frame, text="Scan Types & Options", padding="10")
    n_options_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    n_options_frame.columnconfigure(1, weight=1)

    app_instance.nmap_scan_type_vars = {}
    scan_types = {
        "-sS (TCP SYN)": tk.BooleanVar(value=True), "-sT (TCP Connect)": tk.BooleanVar(),
        "-sU (UDP)": tk.BooleanVar(), "-sA (TCP ACK)": tk.BooleanVar(),
    }
    r, c = 0, 0
    for text, var in scan_types.items():
        app_instance.nmap_scan_type_vars[text] = var
        cb = ttk.Checkbutton(n_options_frame, text=text, variable=var, command=app_instance.update_command_preview)
        cb.grid(row=r, column=c, sticky="w", padx=5, pady=2)
        c += 1
        if c >= 2:
            c = 0
            r += 1
    
    current_row_st = r
    current_col_st = c
    
    app_instance.nmap_ping_scan_var = tk.BooleanVar()
    cb_ping = ttk.Checkbutton(n_options_frame, text="-sn (Ping Scan)", variable=app_instance.nmap_ping_scan_var, command=app_instance.update_command_preview)
    cb_ping.grid(row=current_row_st, column=current_col_st, sticky="w", padx=5, pady=2)
    current_col_st +=1
    if current_col_st >=2: current_col_st =0; current_row_st +=1

    app_instance.nmap_no_ping_var = tk.BooleanVar(value=True)
    cb_noping = ttk.Checkbutton(n_options_frame, text="-Pn (No Ping)", variable=app_instance.nmap_no_ping_var, command=app_instance.update_command_preview)
    cb_noping.grid(row=current_row_st, column=current_col_st, sticky="w", padx=5, pady=2)

    n_detect_frame = ttk.LabelFrame(parent_frame, text="Detection & Output", padding="10")
    n_detect_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    n_detect_frame.columnconfigure(1, weight=1)

    app_instance.nmap_os_detect_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(n_detect_frame, text="-O (OS detection)", variable=app_instance.nmap_os_detect_var, command=app_instance.update_command_preview).grid(row=0, column=0, sticky="w", padx=5, pady=2)
    app_instance.nmap_version_detect_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(n_detect_frame, text="-sV (Service/Version)", variable=app_instance.nmap_version_detect_var, command=app_instance.update_command_preview).grid(row=0, column=1, sticky="w", padx=5, pady=2)
    
    app_instance.nmap_fast_scan_var = tk.BooleanVar()
    ttk.Checkbutton(n_detect_frame, text="-F (Fast mode)", variable=app_instance.nmap_fast_scan_var, command=app_instance.update_command_preview).grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.nmap_verbose_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(n_detect_frame, text="-v (Verbose)", variable=app_instance.nmap_verbose_var, command=app_instance.update_command_preview).grid(row=1, column=1, sticky="w", padx=5, pady=2)

def build_command(app_instance):
    cmd_list = []
    target = app_instance.nmap_target_var.get().strip()
    if not target: raise ValueError("Nmap target cannot be empty.")
    
    temp_cmd_list = [] 
    if app_instance.nmap_ping_scan_var.get():
        temp_cmd_list.append("-sn")
    else:
        selected_scan_type = False
        for type_cmd_full, var in app_instance.nmap_scan_type_vars.items():
            if var.get():
                temp_cmd_list.append(type_cmd_full.split(" ")[0])
                selected_scan_type = True
    if app_instance.nmap_ports_var.get() and not app_instance.nmap_ping_scan_var.get():
        temp_cmd_list.extend(['-p', app_instance.nmap_ports_var.get().strip()])
    if app_instance.nmap_no_ping_var.get(): temp_cmd_list.append("-Pn")
    if app_instance.nmap_os_detect_var.get() and not app_instance.nmap_ping_scan_var.get(): temp_cmd_list.append("-O")
    if app_instance.nmap_version_detect_var.get() and not app_instance.nmap_ping_scan_var.get(): temp_cmd_list.append("-sV")
    if app_instance.nmap_fast_scan_var.get() and not app_instance.nmap_ping_scan_var.get(): temp_cmd_list.append("-F")
    if app_instance.nmap_verbose_var.get(): temp_cmd_list.append("-v")
    
    cmd_list.extend(temp_cmd_list)
    cmd_list.append(target)
    return cmd_list
