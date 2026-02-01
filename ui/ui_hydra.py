import tkinter as tk
from tkinter import ttk
import os

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    ttk.Label(parent_frame, text="Target IP:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    app_instance.hydra_target_var = tk.StringVar()
    t_entry = ttk.Entry(parent_frame, textvariable=app_instance.hydra_target_var, width=30)
    t_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)
    t_entry.bind("<KeyRelease>", app_instance.update_command_preview)

    ttk.Label(parent_frame, text="Service (ssh, ftp, rdp):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.hydra_service_var = tk.StringVar()
    s_entry = ttk.Entry(parent_frame, textvariable=app_instance.hydra_service_var, width=15)
    s_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)
    s_entry.bind("<KeyRelease>", app_instance.update_command_preview)

    # Creds
    creds_frame = ttk.LabelFrame(parent_frame, text="Credentials", padding=5)
    creds_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
    
    ttk.Label(creds_frame, text="Username (-l) or List (-L):").grid(row=0, column=0, sticky="w")
    app_instance.hydra_user_var = tk.StringVar()
    u_entry = ttk.Entry(creds_frame, textvariable=app_instance.hydra_user_var, width=30)
    u_entry.grid(row=0, column=1, sticky="ew")
    u_entry.bind("<KeyRelease>", app_instance.update_command_preview)
    app_instance.hydra_user_is_list = tk.BooleanVar()
    ttk.Checkbutton(creds_frame, text="Is List?", variable=app_instance.hydra_user_is_list, command=app_instance.update_command_preview).grid(row=0, column=2)

    ttk.Label(creds_frame, text="Password (-p) or List (-P):").grid(row=1, column=0, sticky="w")
    app_instance.hydra_pass_var = tk.StringVar()
    p_entry = ttk.Entry(creds_frame, textvariable=app_instance.hydra_pass_var, width=30)
    p_entry.grid(row=1, column=1, sticky="ew")
    p_entry.bind("<KeyRelease>", app_instance.update_command_preview)
    app_instance.hydra_pass_is_list = tk.BooleanVar(value=True)
    ttk.Checkbutton(creds_frame, text="Is List?", variable=app_instance.hydra_pass_is_list, command=app_instance.update_command_preview).grid(row=1, column=2)

def build_command(app_instance):
    cmd_list = ["hydra"]
    
    target = app_instance.hydra_target_var.get().strip()
    service = app_instance.hydra_service_var.get().strip()
    
    if not target or not service:
        raise ValueError("Target and Service are required.")
    
    # Login
    user_val = app_instance.hydra_user_var.get().strip()
    if user_val:
        if app_instance.hydra_user_is_list.get():
            cmd_list.append(f"-L")
            cmd_list.append(user_val)
        else:
            cmd_list.append(f"-l")
            cmd_list.append(user_val)
            
    # Pass
    pass_val = app_instance.hydra_pass_var.get().strip()
    if pass_val:
        if app_instance.hydra_pass_is_list.get():
            cmd_list.append(f"-P")
            cmd_list.append(pass_val)
        else:
            cmd_list.append(f"-p")
            cmd_list.append(pass_val)
            
    cmd_list.append(target)
    cmd_list.append(service)
    
    # Safety fast
    # cmd_list.append("-t")
    # cmd_list.append("4") 
    
    return cmd_list
