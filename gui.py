#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import subprocess
import threading
import queue
import os
import shlex  # For safely splitting command strings
import shutil  # For finding executables
import sys  # For checking platform and exiting
import re  # For parsing output for coloring

# --- Configuration ---
# Attempt to find executables in common paths or rely on PATH
EXECUTABLE_PATHS = {
    'gobuster': ['/usr/bin/gobuster', '/snap/bin/gobuster', 'gobuster'],
    'nmap': ['/usr/bin/nmap', 'nmap'],
    'sqlmap': ['/usr/share/sqlmap/sqlmap.py', 'sqlmap.py', 'sqlmap'],  # sqlmap.py might need python3
    'nikto': ['/usr/bin/nikto', '/opt/nikto/program/nikto.pl', 'nikto.pl', 'nikto'],  # nikto.pl might need perl
    'john': ['/usr/sbin/john', '/opt/john/run/john', 'john']
}

FOUND_EXECUTABLES = {}


def find_executable(tool_name):
    """Finds the specified executable."""
    if tool_name in FOUND_EXECUTABLES and FOUND_EXECUTABLES[tool_name]:
        return FOUND_EXECUTABLES[tool_name]

    paths_to_check = EXECUTABLE_PATHS.get(tool_name, [tool_name])
    for path_candidate in paths_to_check:
        found_path = shutil.which(path_candidate)
        if found_path:
            # Special handling for script-based tools that might need an interpreter
            if tool_name == 'sqlmap' and (found_path.endswith('.py') or 'sqlmap.py' in path_candidate):
                # Check if python3 is available
                if shutil.which('python3'):
                    FOUND_EXECUTABLES[tool_name] = ['python3', found_path]
                    return ['python3', found_path]
                else:
                    continue  # Cannot run .py without python3
            elif tool_name == 'nikto' and (found_path.endswith('.pl') or 'nikto.pl' in path_candidate):
                if shutil.which('perl'):
                    FOUND_EXECUTABLES[tool_name] = ['perl', found_path]
                    return ['perl', found_path]
                else:
                    continue  # Cannot run .pl without perl
            FOUND_EXECUTABLES[tool_name] = [found_path]  # Store as a list for consistency
            return [found_path]
    FOUND_EXECUTABLES[tool_name] = None
    return None


# Initialize found executables
for tool in EXECUTABLE_PATHS.keys():
    find_executable(tool)


# --- Helper Functions ---

def run_command_in_thread(args_list, output_queue, process_queue, stop_event, tool_name="Tool"):
    """
    Runs the command in a subprocess and puts output/errors into a queue.
    Checks a stop_event periodically.
    """
    process = None
    try:
        process = subprocess.Popen(
            args_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        process_queue.put(process)

        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if stop_event.is_set():
                    output_queue.put(f"\n--- {tool_name} scan stopped by user ---")
                    break
                if line:
                    output_queue.put(line)
            process.stdout.close()

        if not stop_event.is_set():
            return_code = process.wait()
            output_queue.put(f"\n--- {tool_name} process finished with exit code {return_code} ---")

    except FileNotFoundError:
        cmd_str = args_list[0] if not isinstance(args_list[0], list) else args_list[0][0]
        output_queue.put(f"ERROR: '{cmd_str}' command not found for {tool_name}.")
        output_queue.put(f"Please ensure {tool_name} is installed and in your PATH or adjust EXECUTABLE_PATHS.")
    except Exception as e:
        output_queue.put(f"\n--- An error occurred during {tool_name} execution: {e} ---")
    finally:
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.5)
                if process.poll() is None:
                    process.kill()
            except Exception as e:
                print(f"Error during final {tool_name} process cleanup: {e}", file=sys.stderr)
                try:
                    output_queue.put(f"\n--- Error during final {tool_name} process cleanup: {e} ---")
                except Exception:
                    pass
        output_queue.put(None)  # Sentinel
        process_queue.put(None)  # Sentinel


# --- Main Application Class ---

class PentestApp:
    def __init__(self, master):
        self.master = master
        master.title("Redboar Pentesting GUI")
        master.geometry("950x750")
        master.minsize(800, 650)

        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        if 'clam' in available_themes:
            self.style.theme_use('clam')
        elif 'alt' in available_themes:
            self.style.theme_use('alt')

        self.process = None
        self.proc_thread = None
        self.output_queue = queue.Queue()
        self.process_queue = queue.Queue()
        self.stop_event = threading.Event()

        self.current_tool_name = tk.StringVar(value="Gobuster")  # Default tool

        self.create_widgets()
        self.update_command_preview()

        master.columnconfigure(0, weight=1)
        master.rowconfigure(1, weight=1)  # Main content area (notebook)
        master.rowconfigure(3, weight=1)  # Output area

        # Check for essential tools on startup (at least Gobuster initially)
        if not FOUND_EXECUTABLES.get('gobuster'):
            messagebox.showerror("Error: Gobuster Not Found",
                                 f"Gobuster executable not found! Checked paths for 'gobuster': {EXECUTABLE_PATHS['gobuster']}\n"
                                 "Application may not function correctly for Gobuster scans.")
        # Configure output tags
        self._configure_output_tags()

    def _configure_output_tags(self):
        self.output_text.tag_configure("status_200", foreground="green")
        self.output_text.tag_configure("status_30x", foreground="blue")
        self.output_text.tag_configure("status_401", foreground="darkorange")
        self.output_text.tag_configure("status_403", foreground="red")
        self.output_text.tag_configure("status_50x", foreground="magenta")
        self.output_text.tag_configure("error", foreground="red", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("info", foreground="grey")
        self.output_text.tag_configure("success", foreground="green", font=('monospace', 10, 'bold'))

        # Nmap specific
        self.output_text.tag_configure("nmap_port_open", foreground="green")
        self.output_text.tag_configure("nmap_port_closed", foreground="red")
        self.output_text.tag_configure("nmap_port_filtered", foreground="orange")
        self.output_text.tag_configure("nmap_host_up", foreground="green")
        self.output_text.tag_configure("nmap_service", foreground="blue")

        # SQLMap specific
        self.output_text.tag_configure("sqlmap_vulnerable", foreground="red", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("sqlmap_info", foreground="cyan")
        self.output_text.tag_configure("sqlmap_dbms", foreground="purple")
        self.output_text.tag_configure("sqlmap_data", foreground="green")

        # Nikto specific
        self.output_text.tag_configure("nikto_vuln", foreground="red", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("nikto_info", foreground="blue")
        self.output_text.tag_configure("nikto_server", foreground="purple")

        # John specific
        self.output_text.tag_configure("john_cracked", foreground="green", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("john_status", foreground="grey")

    def create_widgets(self):
        # --- Main Tool Selection Notebook ---
        self.main_notebook = ttk.Notebook(self.master, padding="5")
        self.main_notebook.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.main_notebook.bind("<<NotebookTabChanged>>", self.on_tool_selected)

        # Create frames for each tool
        self.gobuster_frame = ttk.Frame(self.main_notebook, padding="10")
        self.nmap_frame = ttk.Frame(self.main_notebook, padding="10")
        self.sqlmap_frame = ttk.Frame(self.main_notebook, padding="10")
        self.nikto_frame = ttk.Frame(self.main_notebook, padding="10")
        self.john_frame = ttk.Frame(self.main_notebook, padding="10")

        self.main_notebook.add(self.gobuster_frame, text=' Gobuster ')
        self.main_notebook.add(self.nmap_frame, text=' Nmap ')
        self.main_notebook.add(self.sqlmap_frame, text=' SQLMap ')
        self.main_notebook.add(self.nikto_frame, text=' Nikto ')
        self.main_notebook.add(self.john_frame, text=' John the Ripper ')

        # Populate each tool's frame
        self._create_gobuster_ui(self.gobuster_frame)
        self._create_nmap_ui(self.nmap_frame)
        self._create_sqlmap_ui(self.sqlmap_frame)
        self._create_nikto_ui(self.nikto_frame)
        self._create_john_ui(self.john_frame)

        # --- Command Preview ---
        cmd_frame = ttk.Frame(self.master, padding="5 0")
        cmd_frame.grid(row=1, column=0, sticky="ew", padx=5)
        cmd_frame.columnconfigure(1, weight=1)
        ttk.Label(cmd_frame, text="Command Preview:").grid(row=0, column=0, sticky="w")
        self.cmd_preview_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_frame, textvariable=self.cmd_preview_var, state="readonly", font="monospace 10")
        cmd_entry.grid(row=0, column=1, sticky="ew", padx=5)

        # --- Progress Bar ---
        self.progress_bar = ttk.Progressbar(self.master, mode='indeterminate', length=200)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.progress_bar.grid_remove()  # Initially hidden

        # --- Output Area ---
        output_frame = ttk.Frame(self.master, padding="5")
        output_frame.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=15, font="monospace 10")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_text.configure(state='disabled')

        # --- Control Buttons & Status ---
        control_frame = ttk.Frame(self.master, padding="5")
        control_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=5)
        control_frame.columnconfigure(4, weight=1)  # Push status label to the right

        self.start_button = ttk.Button(control_frame, text="Start Scan", command=self.start_scan)
        self.start_button.grid(row=0, column=0, padx=5)
        self.stop_button = ttk.Button(control_frame, text="Stop Scan", command=self.stop_scan, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)
        self.clear_button = ttk.Button(control_frame, text="Clear Output", command=self.clear_output)
        self.clear_button.grid(row=0, column=2, padx=5)
        self.export_button = ttk.Button(control_frame, text="Export Output", command=self.export_results)
        self.export_button.grid(row=0, column=3, padx=5)
        self.status_label = ttk.Label(control_frame, text="Status: Idle", anchor="e")
        self.status_label.grid(row=0, column=4, sticky="e", padx=5)
        self.exit_button = ttk.Button(control_frame, text="Exit", command=self.master.quit)
        self.exit_button.grid(row=0, column=5, padx=5)

    def on_tool_selected(self, event=None):
        selected_tab_index = self.main_notebook.index(self.main_notebook.select())
        tool_name = self.main_notebook.tab(selected_tab_index, "text").strip()
        self.current_tool_name.set(tool_name)
        self.update_command_preview()
        # Reset status if a tool was running and user switches tabs
        if self.stop_button['state'] == tk.NORMAL:  # if scan was running
            # self.stop_scan() # Optionally stop scan on tab switch, or just update UI
            self.status_label.config(text=f"Status: Switched tool while {self.proc_thread_tool_name} was running.")
            # Keep stop button active if a process is truly running.
            # For simplicity now, we'll assume user stops before switching or it's a visual switch.

    def _create_shared_options_frame(self, parent_frame, tool_vars_prefix):
        """Helper to create common 'Threads' and 'Timeout' options"""
        options_frame = ttk.Frame(parent_frame, padding="5")
        options_frame.grid(row=10, column=0, columnspan=3, sticky="ew", pady=5)  # Adjusted row

        # Threads
        ttk.Label(options_frame, text="Threads:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        setattr(self, f"{tool_vars_prefix}_threads_var", tk.StringVar(value='10'))
        threads_entry = ttk.Entry(options_frame, textvariable=getattr(self, f"{tool_vars_prefix}_threads_var"), width=5)
        threads_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        threads_entry.bind("<KeyRelease>", self.update_command_preview)

        # Timeout (example, adapt per tool)
        ttk.Label(options_frame, text="Timeout (e.g., 10s, 1m):").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        setattr(self, f"{tool_vars_prefix}_timeout_var", tk.StringVar(value='10s'))
        timeout_entry = ttk.Entry(options_frame, textvariable=getattr(self, f"{tool_vars_prefix}_timeout_var"), width=8)
        timeout_entry.grid(row=0, column=3, sticky="w", padx=5, pady=2)
        timeout_entry.bind("<KeyRelease>", self.update_command_preview)
        return options_frame

    # --- Gobuster UI ---
    def _create_gobuster_ui(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        ttk.Label(parent_frame, text="Mode:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.gobuster_modes = {'Directory/File': 'dir', 'DNS Subdomain': 'dns', 'Virtual Host': 'vhost'}
        self.gobuster_current_mode_var = tk.StringVar(value='Directory/File')
        self.gobuster_mode_combo = ttk.Combobox(parent_frame, textvariable=self.gobuster_current_mode_var,
                                                values=list(self.gobuster_modes.keys()), state="readonly", width=15)
        self.gobuster_mode_combo.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.gobuster_mode_combo.bind("<<ComboboxSelected>>", self.update_command_preview)

        ttk.Label(parent_frame, text="Target URL/Domain:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.gobuster_target_var = tk.StringVar()
        self.gobuster_target_entry = ttk.Entry(parent_frame, textvariable=self.gobuster_target_var, width=50)
        self.gobuster_target_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self.gobuster_target_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(parent_frame, text="Wordlist:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.gobuster_wordlist_var = tk.StringVar()
        self.gobuster_wordlist_entry = ttk.Entry(parent_frame, textvariable=self.gobuster_wordlist_var, width=50)
        self.gobuster_wordlist_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.gobuster_wordlist_entry.bind("<KeyRelease>", self.update_command_preview)
        self.gobuster_browse_button = ttk.Button(parent_frame, text="Browse...",
                                                 command=lambda: self.browse_file(self.gobuster_wordlist_var))
        self.gobuster_browse_button.grid(row=2, column=2, sticky="e", padx=5, pady=2)

        # Gobuster specific options (simplified from original, add tabs if needed)
        g_options_frame = ttk.Frame(parent_frame, padding="5")
        g_options_frame.grid(row=3, column=0, columnspan=3, sticky="ew")

        self.gobuster_threads_var = tk.StringVar(value='10')
        ttk.Label(g_options_frame, text="Threads (-t):").grid(row=0, column=0, sticky="w")
        ttk.Entry(g_options_frame, textvariable=self.gobuster_threads_var, width=5).grid(row=0, column=1, sticky="w")

        self.gobuster_extensions_var = tk.StringVar()
        ttk.Label(g_options_frame, text="Extensions (-x, comma separated):").grid(row=1, column=0, sticky="w")
        ttk.Entry(g_options_frame, textvariable=self.gobuster_extensions_var, width=20).grid(row=1, column=1,
                                                                                             sticky="w")

        self.gobuster_status_codes_var = tk.StringVar(value='200,204,301,302,307,401,403')
        ttk.Label(g_options_frame, text="Include Codes (-s):").grid(row=2, column=0, sticky="w")
        ttk.Entry(g_options_frame, textvariable=self.gobuster_status_codes_var, width=30).grid(row=2, column=1,
                                                                                               sticky="w")

        # Bind all relevant gobuster var changes to update preview
        for var in [self.gobuster_threads_var, self.gobuster_extensions_var, self.gobuster_status_codes_var]:
            var.trace_add("write", lambda *args: self.update_command_preview())

    # --- Nmap UI ---
    def _create_nmap_ui(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        ttk.Label(parent_frame, text="Target(s):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.nmap_target_var = tk.StringVar()
        self.nmap_target_entry = ttk.Entry(parent_frame, textvariable=self.nmap_target_var, width=50)
        self.nmap_target_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self.nmap_target_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(parent_frame, text="Ports (e.g., 22,80,443 or 1-1000):").grid(row=1, column=0, sticky="w", padx=5,
                                                                                pady=2)
        self.nmap_ports_var = tk.StringVar()
        self.nmap_ports_entry = ttk.Entry(parent_frame, textvariable=self.nmap_ports_var, width=30)
        self.nmap_ports_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.nmap_ports_entry.bind("<KeyRelease>", self.update_command_preview)

        n_options_frame = ttk.Frame(parent_frame, padding="5")
        n_options_frame.grid(row=2, column=0, columnspan=3, sticky="ew")

        self.nmap_scan_type_vars = {}
        scan_types = {
            "-sS (TCP SYN)": tk.BooleanVar(value=True),
            "-sT (TCP Connect)": tk.BooleanVar(),
            "-sU (UDP)": tk.BooleanVar(),
            "-sA (TCP ACK)": tk.BooleanVar(),
        }
        r = 0
        for text, var in scan_types.items():
            self.nmap_scan_type_vars[text] = var
            ttk.Checkbutton(n_options_frame, text=text, variable=var, command=self.update_command_preview).grid(row=r,
                                                                                                                column=0,
                                                                                                                sticky="w")
            r += 1

        self.nmap_ping_scan_var = tk.BooleanVar()
        ttk.Checkbutton(n_options_frame, text="-sn (Ping Scan - No Ports)", variable=self.nmap_ping_scan_var,
                        command=self.update_command_preview).grid(row=r, column=0, sticky="w")
        r += 1
        self.nmap_no_ping_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(n_options_frame, text="-Pn (Treat all hosts as online)", variable=self.nmap_no_ping_var,
                        command=self.update_command_preview).grid(row=r, column=0, sticky="w")

        n_detect_frame = ttk.Frame(parent_frame, padding="5")
        n_detect_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.nmap_os_detect_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(n_detect_frame, text="-O (Enable OS detection)", variable=self.nmap_os_detect_var,
                        command=self.update_command_preview).grid(row=0, column=0, sticky="w")
        self.nmap_version_detect_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(n_detect_frame, text="-sV (Service/Version detection)", variable=self.nmap_version_detect_var,
                        command=self.update_command_preview).grid(row=0, column=1, sticky="w")
        self.nmap_fast_scan_var = tk.BooleanVar()
        ttk.Checkbutton(n_detect_frame, text="-F (Fast mode - fewer ports)", variable=self.nmap_fast_scan_var,
                        command=self.update_command_preview).grid(row=1, column=0, sticky="w")
        self.nmap_verbose_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(n_detect_frame, text="-v (Verbose)", variable=self.nmap_verbose_var,
                        command=self.update_command_preview).grid(row=1, column=1, sticky="w")

    # --- SQLMap UI ---
    def _create_sqlmap_ui(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        ttk.Label(parent_frame, text="Target URL (-u):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.sqlmap_target_var = tk.StringVar()
        self.sqlmap_target_entry = ttk.Entry(parent_frame, textvariable=self.sqlmap_target_var, width=50)
        self.sqlmap_target_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self.sqlmap_target_entry.bind("<KeyRelease>", self.update_command_preview)

        s_options_frame = ttk.Frame(parent_frame, padding="5")
        s_options_frame.grid(row=1, column=0, columnspan=3, sticky="ew")

        self.sqlmap_batch_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(s_options_frame, text="--batch (Non-interactive)", variable=self.sqlmap_batch_var,
                        command=self.update_command_preview).grid(row=0, column=0, sticky="w")

        self.sqlmap_dbs_var = tk.BooleanVar()
        ttk.Checkbutton(s_options_frame, text="--dbs (Enumerate databases)", variable=self.sqlmap_dbs_var,
                        command=self.update_command_preview).grid(row=1, column=0, sticky="w")
        self.sqlmap_current_db_var = tk.BooleanVar()
        ttk.Checkbutton(s_options_frame, text="--current-db (Retrieve current DB)", variable=self.sqlmap_current_db_var,
                        command=self.update_command_preview).grid(row=1, column=1, sticky="w")

        self.sqlmap_tables_var = tk.BooleanVar()
        ttk.Checkbutton(s_options_frame, text="--tables (Enumerate tables for DB)", variable=self.sqlmap_tables_var,
                        command=self.update_command_preview).grid(row=2, column=0, sticky="w")
        self.sqlmap_dump_var = tk.BooleanVar()
        ttk.Checkbutton(s_options_frame, text="--dump (Dump table entries)", variable=self.sqlmap_dump_var,
                        command=self.update_command_preview).grid(row=2, column=1, sticky="w")

        ttk.Label(s_options_frame, text="Specify DB (-D):").grid(row=3, column=0, sticky="w")
        self.sqlmap_db_name_var = tk.StringVar()
        ttk.Entry(s_options_frame, textvariable=self.sqlmap_db_name_var, width=15).grid(row=3, column=1, sticky="w")
        self.sqlmap_db_name_var.trace_add("write", lambda *args: self.update_command_preview())

        ttk.Label(s_options_frame, text="Specify Table (-T):").grid(row=4, column=0, sticky="w")
        self.sqlmap_table_name_var = tk.StringVar()
        ttk.Entry(s_options_frame, textvariable=self.sqlmap_table_name_var, width=15).grid(row=4, column=1, sticky="w")
        self.sqlmap_table_name_var.trace_add("write", lambda *args: self.update_command_preview())

        ttk.Label(s_options_frame, text="Level (1-5):").grid(row=5, column=0, sticky="w")
        self.sqlmap_level_var = tk.StringVar(value="1")
        ttk.Entry(s_options_frame, textvariable=self.sqlmap_level_var, width=3).grid(row=5, column=1, sticky="w")
        self.sqlmap_level_var.trace_add("write", lambda *args: self.update_command_preview())

        ttk.Label(s_options_frame, text="Risk (1-3):").grid(row=6, column=0, sticky="w")
        self.sqlmap_risk_var = tk.StringVar(value="1")
        ttk.Entry(s_options_frame, textvariable=self.sqlmap_risk_var, width=3).grid(row=6, column=1, sticky="w")
        self.sqlmap_risk_var.trace_add("write", lambda *args: self.update_command_preview())

    # --- Nikto UI ---
    def _create_nikto_ui(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        ttk.Label(parent_frame, text="Target Host/URL (-h):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.nikto_target_var = tk.StringVar()
        self.nikto_target_entry = ttk.Entry(parent_frame, textvariable=self.nikto_target_var, width=50)
        self.nikto_target_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self.nikto_target_entry.bind("<KeyRelease>", self.update_command_preview)

        k_options_frame = ttk.Frame(parent_frame, padding="5")
        k_options_frame.grid(row=1, column=0, columnspan=3, sticky="ew")

        ttk.Label(k_options_frame, text="Output Format (-Format):").grid(row=0, column=0, sticky="w")
        self.nikto_format_var = tk.StringVar(value="txt")
        self.nikto_format_combo = ttk.Combobox(k_options_frame, textvariable=self.nikto_format_var,
                                               values=['txt', 'csv', 'htm', 'xml'], state="readonly", width=5)
        self.nikto_format_combo.grid(row=0, column=1, sticky="w")
        self.nikto_format_combo.bind("<<ComboboxSelected>>", self.update_command_preview)

        ttk.Label(k_options_frame, text="Tuning (-Tuning x):").grid(row=1, column=0, sticky="w")
        self.nikto_tuning_var = tk.StringVar(value="x 123b")  # Default fairly comprehensive
        # Example tuning options: 0 File Upload, 1 Interesting File, 2 Misconfiguration, 3 Information Disclosure, etc.
        self.nikto_tuning_combo = ttk.Combobox(k_options_frame, textvariable=self.nikto_tuning_var,
                                               values=['x 123b', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a',
                                                       'b', 'c', 'd', 'e'], width=15)
        self.nikto_tuning_combo.grid(row=1, column=1, sticky="w")
        self.nikto_tuning_combo.bind("<<ComboboxSelected>>", self.update_command_preview)

        self.nikto_ssl_var = tk.BooleanVar()
        ttk.Checkbutton(k_options_frame, text="-ssl (Force SSL mode)", variable=self.nikto_ssl_var,
                        command=self.update_command_preview).grid(row=2, column=0, sticky="w")
        self.nikto_ask_no_var = tk.BooleanVar(value=True)  # Useful for GUI
        ttk.Checkbutton(k_options_frame, text="-ask no (Auto 'no' to prompts)", variable=self.nikto_ask_no_var,
                        command=self.update_command_preview).grid(row=2, column=1, sticky="w")

    # --- John the Ripper UI ---
    def _create_john_ui(self, parent_frame):
        parent_frame.columnconfigure(1, weight=1)
        ttk.Label(parent_frame, text="Hash File:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.john_hash_file_var = tk.StringVar()
        self.john_hash_file_entry = ttk.Entry(parent_frame, textvariable=self.john_hash_file_var, width=40)
        self.john_hash_file_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.john_hash_file_entry.bind("<KeyRelease>", self.update_command_preview)
        self.john_browse_hash_button = ttk.Button(parent_frame, text="Browse...",
                                                  command=lambda: self.browse_file(self.john_hash_file_var))
        self.john_browse_hash_button.grid(row=0, column=2, sticky="e", padx=5, pady=2)

        j_options_frame = ttk.Frame(parent_frame, padding="5")
        j_options_frame.grid(row=1, column=0, columnspan=3, sticky="ew")

        ttk.Label(j_options_frame, text="Wordlist (Optional):").grid(row=0, column=0, sticky="w")
        self.john_wordlist_var = tk.StringVar()
        self.john_wordlist_entry = ttk.Entry(j_options_frame, textvariable=self.john_wordlist_var, width=30)
        self.john_wordlist_entry.grid(row=0, column=1, sticky="ew")
        self.john_browse_wordlist_button = ttk.Button(j_options_frame, text="Browse...",
                                                      command=lambda: self.browse_file(self.john_wordlist_var))
        self.john_browse_wordlist_button.grid(row=0, column=2, sticky="e")
        self.john_wordlist_var.trace_add("write", lambda *args: self.update_command_preview())

        ttk.Label(j_options_frame, text="Format (Optional):").grid(row=1, column=0, sticky="w")
        self.john_format_var = tk.StringVar()
        ttk.Entry(j_options_frame, textvariable=self.john_format_var, width=15).grid(row=1, column=1, sticky="w")
        self.john_format_var.trace_add("write", lambda *args: self.update_command_preview())

        ttk.Label(j_options_frame, text="Session Name (Optional):").grid(row=2, column=0, sticky="w")
        self.john_session_var = tk.StringVar()
        ttk.Entry(j_options_frame, textvariable=self.john_session_var, width=15).grid(row=2, column=1, sticky="w")
        self.john_session_var.trace_add("write", lambda *args: self.update_command_preview())

        self.john_show_cracked_var = tk.BooleanVar()
        ttk.Checkbutton(j_options_frame, text="--show (Show cracked for session)", variable=self.john_show_cracked_var,
                        command=self.update_command_preview).grid(row=3, column=0, sticky="w")

    def browse_file(self, string_var_to_set, title="Select File"):
        filename = filedialog.askopenfilename(title=title)
        if filename:
            string_var_to_set.set(filename)
            self.update_command_preview()

    def apply_coloring(self, line_with_newline):
        """Applies syntax highlighting tags based on line content."""
        line = line_with_newline.strip()
        tags = ()
        tool = self.current_tool_name.get()

        if "ERROR:" in line or "Error:" in line or "Failed" in line or "Traceback" in line:
            tags = ("error",)
        elif line.startswith("---") or line.startswith("===") or line.startswith("[*]") or line.startswith(
                "[+]") or line.startswith("[INFO]"):
            tags = ("info",)

        if tool == "Gobuster":
            match_status = re.match(r'.*\(Status: (\d{3})\)', line)
            if match_status:
                status_code = int(match_status.group(1))
                if status_code == 200:
                    tags = ("status_200",)
                elif 300 <= status_code < 400:
                    tags = ("status_30x",)
                elif status_code == 401:
                    tags = ("status_401",)
                elif status_code == 403:
                    tags = ("status_403",)
                elif 500 <= status_code < 600:
                    tags = ("status_50x",)
            elif line.startswith("Found:"):
                tags = ("success",)  # For DNS/VHOST
        elif tool == "Nmap":
            if "Host is up" in line:
                tags = ("nmap_host_up", "info")
            elif "/open" in line:
                tags = ("nmap_port_open",)
            elif "/closed" in line:
                tags = ("nmap_port_closed",)
            elif "/filtered" in line:
                tags = ("nmap_port_filtered",)
            if "Service Info:" in line or "OS details:" in line: tags = ("nmap_service", "info")
        elif tool == "SQLMap":
            if "vulnerable" in line.lower(): tags = ("sqlmap_vulnerable",)
            if "fetched data" in line.lower() or line.startswith("["): tags = ("sqlmap_data",)  # Simple catch for data
            if "DBMS" in line: tags = ("sqlmap_dbms",)
            if line.startswith("[INFO]") or line.startswith("[DEBUG]") or line.startswith("[WARNING]"): tags = (
            "sqlmap_info",)  # Override general info for more specific
        elif tool == "Nikto":
            if line.startswith("+") and ("OSVDB" in line or "vulnerability" in line.lower()):
                tags = ("nikto_vuln",)
            elif line.startswith("+ Server:"):
                tags = ("nikto_server",)
            elif line.startswith("+"):
                tags = ("nikto_info",)  # General Nikto findings
        elif tool == "John the Ripper":
            # Simple check for cracked password line (usually "password (username)" format, but can vary)
            if re.match(r'^\S+\s+\(\S*\)\s*$', line) and not line.startswith("Loaded") and not line.startswith(
                    "Proceeding"):
                # This is a very basic pattern, John's output can be complex
                # Check if it's not a status line like "0g 0:00:00:00 DONE"
                if not re.match(r'^\d+g \d+:\d+:\d+:\d+.*', line):
                    tags = ("john_cracked",)
            elif "guesses:" in line or "Proceeding with" in line or "Loaded" in line:
                tags = ("john_status",)

        return line_with_newline, tags

    def update_output(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line is None:  # Sentinel
                    self.set_scan_state(running=False, status="Finished")
                    return
                else:
                    self.output_text.configure(state='normal')
                    colored_line, tags = self.apply_coloring(line)
                    self.output_text.insert(tk.END, colored_line, tags)
                    self.output_text.see(tk.END)
                    self.output_text.configure(state='disabled')
        except queue.Empty:
            if self.proc_thread and self.proc_thread.is_alive():
                self.master.after(100, self.update_output)
            elif self.stop_button['state'] == tk.NORMAL:  # Scan was running
                self.set_scan_state(running=False, status="Error/Unexpected Finish")

    def _get_command_for_current_tool(self):
        tool_name = self.current_tool_name.get()
        cmd_list = []
        executable = FOUND_EXECUTABLES.get(tool_name.lower().replace(" ", ""))

        if not executable:
            raise ValueError(f"{tool_name} executable not found. Please check installation and PATH.")

        cmd_list.extend(executable)  # Add the executable path (could be ['python3', 'script.py'])

        if tool_name == "Gobuster":
            mode_cmd = self.gobuster_modes.get(self.gobuster_current_mode_var.get())
            target = self.gobuster_target_var.get().strip()
            wordlist = self.gobuster_wordlist_var.get().strip()
            if not mode_cmd: raise ValueError("Invalid Gobuster mode.")
            if not target: raise ValueError("Gobuster target cannot be empty.")
            if not wordlist: raise ValueError("Gobuster wordlist cannot be empty.")
            if not os.path.exists(wordlist): raise ValueError(f"Gobuster wordlist not found: {wordlist}")

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
            cmd_list.extend(['-t', self.gobuster_threads_var.get().strip()])
            if self.gobuster_extensions_var.get(): cmd_list.extend(['-x', self.gobuster_extensions_var.get().strip()])
            if self.gobuster_status_codes_var.get(): cmd_list.extend(
                ['-s', self.gobuster_status_codes_var.get().strip()])
            cmd_list.append('--no-progress')  # Always for GUI

        elif tool_name == "Nmap":
            target = self.nmap_target_var.get().strip()
            if not target: raise ValueError("Nmap target cannot be empty.")
            cmd_list.append(target)
            if self.nmap_ports_var.get(): cmd_list.extend(['-p', self.nmap_ports_var.get().strip()])

            selected_scan_type = False
            for type_cmd, var in self.nmap_scan_type_vars.items():
                if var.get():
                    cmd_list.append(type_cmd.split(" ")[0])  # e.g., -sS
                    selected_scan_type = True

            if self.nmap_ping_scan_var.get():
                cmd_list.append("-sn")
            elif not selected_scan_type and not self.nmap_fast_scan_var.get() and not self.nmap_ports_var.get():  # If no specific port scan, add a default if not ping
                pass  # Nmap will do default scan if no type specified and not -sn

            if self.nmap_no_ping_var.get(): cmd_list.append("-Pn")
            if self.nmap_os_detect_var.get(): cmd_list.append("-O")
            if self.nmap_version_detect_var.get(): cmd_list.append("-sV")
            if self.nmap_fast_scan_var.get(): cmd_list.append("-F")
            if self.nmap_verbose_var.get(): cmd_list.append("-v")


        elif tool_name == "SQLMap":
            target = self.sqlmap_target_var.get().strip()
            if not target: raise ValueError("SQLMap target URL cannot be empty.")
            cmd_list.extend(['-u', target])
            if self.sqlmap_batch_var.get(): cmd_list.append("--batch")
            if self.sqlmap_dbs_var.get(): cmd_list.append("--dbs")
            if self.sqlmap_current_db_var.get(): cmd_list.append("--current-db")
            if self.sqlmap_db_name_var.get(): cmd_list.extend(['-D', self.sqlmap_db_name_var.get().strip()])
            if self.sqlmap_tables_var.get(): cmd_list.append("--tables")
            if self.sqlmap_table_name_var.get(): cmd_list.extend(['-T', self.sqlmap_table_name_var.get().strip()])
            if self.sqlmap_dump_var.get(): cmd_list.append("--dump")
            if self.sqlmap_level_var.get(): cmd_list.extend(["--level", self.sqlmap_level_var.get().strip()])
            if self.sqlmap_risk_var.get(): cmd_list.extend(["--risk", self.sqlmap_risk_var.get().strip()])


        elif tool_name == "Nikto":
            target = self.nikto_target_var.get().strip()
            if not target: raise ValueError("Nikto target cannot be empty.")
            cmd_list.extend(['-h', target])
            if self.nikto_format_var.get(): cmd_list.extend(['-Format', self.nikto_format_var.get()])
            if self.nikto_tuning_var.get(): cmd_list.extend(['-Tuning', self.nikto_tuning_var.get()])
            if self.nikto_ssl_var.get(): cmd_list.append("-ssl")
            if self.nikto_ask_no_var.get(): cmd_list.append(
                "-ask")  # 'no' is implied by just -ask for some versions, others need 'no' explicitly.
            # Nikto docs say: -ask auto|all|none|no - default: auto
            # for GUI, 'no' or 'none' is best. 'auto' might still prompt. Using 'no'.


        elif tool_name == "John the Ripper":
            hash_file = self.john_hash_file_var.get().strip()
            if not hash_file: raise ValueError("John hash file cannot be empty.")
            if not os.path.exists(hash_file): raise ValueError(f"John hash file not found: {hash_file}")

            if self.john_show_cracked_var.get():
                cmd_list.append("--show")
                cmd_list.append(hash_file)  # For --show, hash_file is an argument to --show typically
                if self.john_session_var.get():  # Show for a specific session
                    cmd_list.extend([f"--session={self.john_session_var.get().strip()}"])  # John takes --session=name
            else:  # Normal cracking mode
                cmd_list.append(hash_file)
                if self.john_wordlist_var.get():
                    wordlist = self.john_wordlist_var.get().strip()
                    if not os.path.exists(wordlist): raise ValueError(f"John wordlist not found: {wordlist}")
                    cmd_list.append(f"--wordlist={wordlist}")
                if self.john_format_var.get(): cmd_list.append(f"--format={self.john_format_var.get().strip()}")
                if self.john_session_var.get(): cmd_list.append(f"--session={self.john_session_var.get().strip()}")

        return cmd_list

    def update_command_preview(self, event=None):
        try:
            cmd_list = self._get_command_for_current_tool()
            # Handle cases where executable itself is a list (e.g. ['python3', 'script.py'])
            quoted_cmd_list = []
            for item in cmd_list:
                if isinstance(item,
                              list):  # Should not happen if find_executable returns a flat list for FOUND_EXECUTABLES[tool_name]
                    quoted_cmd_list.extend(map(shlex.quote, item))
                else:
                    quoted_cmd_list.append(shlex.quote(item))
            preview_text = " ".join(quoted_cmd_list)
            self.cmd_preview_var.set(preview_text)
        except ValueError as e:
            self.cmd_preview_var.set(f"Error: {e}")
        except Exception as e:
            self.cmd_preview_var.set(f"Error building preview: {type(e).__name__} {e}")

    def set_scan_state(self, running: bool, status: str):
        self.start_button.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL if running else tk.DISABLED)
        self.status_label.config(text=f"Status: {status}")
        if running:
            self.progress_bar.grid()
            self.progress_bar.start(10)
        else:
            self.progress_bar.stop()
            self.progress_bar.grid_remove()

    def start_scan(self):
        if self.proc_thread and self.proc_thread.is_alive():
            messagebox.showwarning("Scan Active", f"A {self.proc_thread_tool_name} scan is already running.")
            return

        current_tool = self.current_tool_name.get()
        if not FOUND_EXECUTABLES.get(current_tool.lower().replace(" ", "")):
            messagebox.showerror("Tool Not Found", f"{current_tool} executable not found. Cannot start scan.")
            return

        try:
            args_list = self._get_command_for_current_tool()
            self.output_text.configure(state='normal')
            self.output_text.delete('1.0', tk.END)
            cmd_preview_for_log = " ".join(map(shlex.quote, args_list))
            self.output_text.insert(tk.END, f"Starting {current_tool}: {cmd_preview_for_log}\n\n", ("info",))
            self.output_text.configure(state='disabled')
            self.set_scan_state(running=True, status=f"Running {current_tool}...")

            self.stop_event.clear()
            while not self.output_queue.empty(): self.output_queue.get()
            while not self.process_queue.empty(): self.process_queue.get()

            self.proc_thread_tool_name = current_tool  # Store which tool is running
            self.proc_thread = threading.Thread(
                target=run_command_in_thread,
                args=(args_list, self.output_queue, self.process_queue, self.stop_event, current_tool),
                daemon=True
            )
            self.proc_thread.start()
            self.master.after(100, self.update_output)

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            self.set_scan_state(running=False, status="Input Error")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start {current_tool}:\n{type(e).__name__}: {e}")
            self.set_scan_state(running=False, status="Error")

    def stop_scan(self):
        tool_name = self.proc_thread_tool_name if hasattr(self, 'proc_thread_tool_name') else "Scan"
        self.set_scan_state(running=False, status=f"Stopping {tool_name}...")
        self.stop_event.set()

        proc_to_stop = None
        try:
            proc_to_stop = self.process_queue.get_nowait()
        except queue.Empty:
            self.insert_output_line(f"\n--- Stop requested, but {tool_name} process not found in queue ---", ("info",))
        except Exception as e:
            self.insert_output_line(f"\n--- Error getting {tool_name} process from queue for stop: {e} ---", ("error",))

        if proc_to_stop and proc_to_stop.poll() is None:
            self.insert_output_line(f"\n--- Sending terminate signal to {tool_name} ---", ("info",))
            try:
                proc_to_stop.terminate()
                try:
                    proc_to_stop.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    self.insert_output_line(
                        f"\n--- {tool_name} process did not terminate quickly, sending kill signal ---", ("error",))
                    proc_to_stop.kill()
            except Exception as e:
                self.insert_output_line(f"\n--- Error trying to stop {tool_name} process: {e} ---", ("error",))

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text=f"Status: {tool_name} stopped by user")
        self.progress_bar.stop()
        self.progress_bar.grid_remove()

    def insert_output_line(self, line, tags=()):
        try:
            self.output_text.configure(state='normal')
            self.output_text.insert(tk.END, line + "\n", tags)  # Ensure newline
            self.output_text.see(tk.END)
            self.output_text.configure(state='disabled')
        except tk.TclError:
            print("Warning: Could not write to output widget (likely closing).")
        except Exception as e:
            print(f"Error inserting output line: {e}")

    def clear_output(self):
        self.output_text.configure(state='normal')
        self.output_text.delete('1.0', tk.END)
        self.output_text.configure(state='disabled')

    def export_results(self):
        output_content = self.output_text.get("1.0", tk.END).strip()
        if not output_content:
            messagebox.showwarning("Export Empty", "There is no output to export.")
            return
        filepath = filedialog.asksaveasfilename(
            title="Save Output",
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(output_content)
                messagebox.showinfo("Export Successful", f"Output saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to save file:\n{e}")


# --- Main Execution ---
if __name__ == '__main__':
    try:
        root = tk.Tk()
    except tk.TclError:
        print("ERROR: Tkinter is not available or configured correctly.", file=sys.stderr)
        print("On Debian/Ubuntu/Kali, try: sudo apt update && sudo apt install python3-tk", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred initializing Tkinter: {e}", file=sys.stderr)
        sys.exit(1)

    # Check for executables after root window is created (for potential dialogs if needed later)
    missing_tools = []
    for tool_name_key in EXECUTABLE_PATHS.keys():
        if not FOUND_EXECUTABLES.get(tool_name_key):
            missing_tools.append(tool_name_key.capitalize())

    if missing_tools:
        messagebox.showwarning("Missing Tools",
                               f"The following tools could not be found automatically:\n- {', '.join(missing_tools)}\n"
                               "Functionality for these tools will be unavailable or may fail.\n"
                               "Please ensure they are installed and in your system PATH, or configure paths in the script.")

    app = PentestApp(root)
    root.mainloop()