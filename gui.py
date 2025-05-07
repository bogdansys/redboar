#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import threading
import queue
import os
import shlex # For safely splitting command strings if needed
import shutil # For finding the executable
import sys # For checking platform and exiting
import re # For parsing output for coloring

# --- Configuration ---
# Attempt to find gobuster in common Kali paths or rely on PATH
GOBUSTER_PATHS = ['/usr/bin/gobuster', '/snap/bin/gobuster', 'gobuster']

def find_gobuster():
    """Finds the gobuster executable."""
    for path in GOBUSTER_PATHS:
        found_path = shutil.which(path)
        if found_path:
            return found_path
    return None

GOBUSTER_CMD = find_gobuster()

# --- Helper Functions ---

def run_gobuster(args_list, output_queue, process_queue, stop_event):
    """
    Runs the gobuster command in a subprocess and puts output/errors into a queue.
    Checks a stop_event periodically.

    Args:
        args_list (list): The list of command arguments for gobuster.
        output_queue (queue.Queue): Queue to send stdout/stderr lines to the GUI.
        process_queue (queue.Queue): Queue to put the subprocess object for cancellation.
        stop_event (threading.Event): Event to signal the thread should stop.
    """
    process = None
    try:
        # Start the gobuster process
        process = subprocess.Popen(
            args_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Redirect stderr to stdout
            text=True,
            bufsize=1,
            universal_newlines=True,
            # Use different process creation flags for Windows if needed
            # creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        process_queue.put(process) # Make process available for termination

        # Read output line by line
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if stop_event.is_set(): # Check if stop was requested
                    output_queue.put("\n--- Scan stopped by user ---")
                    break
                if line:
                    output_queue.put(line)
            process.stdout.close()

        if not stop_event.is_set():
             # Wait for the process to finish if not stopped
            return_code = process.wait()
            output_queue.put(f"\n--- Gobuster process finished with exit code {return_code} ---")

    except FileNotFoundError:
        output_queue.put(f"ERROR: '{args_list[0]}' command not found.")
        output_queue.put(f"Please ensure gobuster is installed and in your PATH or adjust GOBUSTER_PATHS (currently checks: {GOBUSTER_PATHS}).")
    except Exception as e:
        output_queue.put(f"\n--- An error occurred during execution: {e} ---")
    finally:
        # Clean up: Ensure process is terminated if it's still running
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.5)
                if process.poll() is None:
                    process.kill()
            except Exception as e:
                 # Avoid printing directly if GUI might be gone
                 print(f"Error during final process cleanup: {e}", file=sys.stderr)
                 try:
                    output_queue.put(f"\n--- Error during final process cleanup: {e} ---")
                 except Exception:
                    pass # Ignore if queue is unusable
        # Signal that the thread is done
        output_queue.put(None) # Sentinel value
        process_queue.put(None) # Sentinel value


# --- Main Application Class ---

class GobusterApp:
    def __init__(self, master):
        self.master = master
        master.title("Gobuster GUI (Tkinter)")
        master.geometry("850x700") # Increased size for tabs
        master.minsize(750, 600) # Adjusted minimum size

        # --- Style ---
        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        # Prefer 'clam' or 'alt' for a decent look on Linux/Mac
        if 'clam' in available_themes: self.style.theme_use('clam')
        elif 'alt' in available_themes: self.style.theme_use('alt')
        # Configure styles for colored output tags
        self.style.configure("Status200.TLabel", foreground="green")
        self.style.configure("Status30x.TLabel", foreground="blue")
        self.style.configure("Status401.TLabel", foreground="orange")
        self.style.configure("Status403.TLabel", foreground="red")
        self.style.configure("Status50x.TLabel", foreground="magenta")
        self.style.configure("StatusError.TLabel", foreground="red", font=('monospace', 10, 'bold'))
        self.style.configure("StatusInfo.TLabel", foreground="grey")

        # --- State Variables ---
        self.process = None
        self.proc_thread = None
        self.output_queue = queue.Queue()
        self.process_queue = queue.Queue()
        self.stop_event = threading.Event()

        # --- Gobuster Modes ---
        self.modes = {
            'Directory/File': 'dir',
            'DNS Subdomain': 'dns',
            'Virtual Host': 'vhost',
        }
        self.current_mode = tk.StringVar(value='Directory/File')

        # --- Build the GUI ---
        self.create_widgets()
        self.update_command_preview() # Initial preview

        # Configure resizing behavior
        master.columnconfigure(0, weight=1)
        master.rowconfigure(4, weight=1) # Make output area expand (row index changed due to progress bar)

        # Check for gobuster on startup
        if not GOBUSTER_CMD:
            messagebox.showerror("Error: Gobuster Not Found",
                                 f"Gobuster executable not found!\nChecked paths: {GOBUSTER_PATHS}\nPlease install gobuster or adjust GOBUSTER_PATHS in the script.")
            master.quit() # Exit if not found

        # Configure tags for output coloring
        self.output_text.tag_configure("status_200", foreground="green")
        self.output_text.tag_configure("status_30x", foreground="blue")
        self.output_text.tag_configure("status_401", foreground="darkorange")
        self.output_text.tag_configure("status_403", foreground="red")
        self.output_text.tag_configure("status_50x", foreground="magenta")
        self.output_text.tag_configure("error", foreground="red", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("info", foreground="grey")
        self.output_text.tag_configure("dns", foreground="purple") # For DNS results
        self.output_text.tag_configure("vhost", foreground="teal") # For VHOST results


    def create_widgets(self):
        """Creates all the GUI elements."""

        # --- Top Frame (Mode, Target, Wordlist) ---
        top_frame = ttk.Frame(self.master, padding="10")
        top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        top_frame.columnconfigure(1, weight=1) # Make entry fields expand

        ttk.Label(top_frame, text="Mode:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.mode_combo = ttk.Combobox(top_frame, textvariable=self.current_mode,
                                       values=list(self.modes.keys()), state="readonly", width=15)
        self.mode_combo.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_change)

        ttk.Label(top_frame, text="Target URL/Domain:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.target_entry = ttk.Entry(top_frame, width=50)
        self.target_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self.target_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(top_frame, text="Wordlist:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.wordlist_entry = ttk.Entry(top_frame, width=50)
        self.wordlist_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.wordlist_entry.bind("<KeyRelease>", self.update_command_preview)
        self.browse_button = ttk.Button(top_frame, text="Browse...", command=self.browse_wordlist)
        self.browse_button.grid(row=2, column=2, sticky="e", padx=5, pady=2)

        # --- Options Tabs ---
        self.notebook = ttk.Notebook(self.master, padding="5")
        self.notebook.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        # Create frames for each tab
        self.tab_common = ttk.Frame(self.notebook, padding="10")
        self.tab_mode_specific = ttk.Frame(self.notebook, padding="10")
        self.tab_network = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.tab_common, text=' Common ')
        self.notebook.add(self.tab_mode_specific, text=' Mode Specific ')
        self.notebook.add(self.tab_network, text=' Network ')

        # Populate Common Tab
        self.create_common_options(self.tab_common)

        # Populate Mode Specific Tab (frames will be added/removed here)
        self.create_dir_options(self.tab_mode_specific)
        self.create_dns_options(self.tab_mode_specific)
        self.create_vhost_options(self.tab_mode_specific)

        # Populate Network Tab
        self.create_network_options(self.tab_network)


        # --- Command Preview ---
        cmd_frame = ttk.Frame(self.master, padding="5 0")
        cmd_frame.grid(row=2, column=0, sticky="ew", padx=5)
        cmd_frame.columnconfigure(1, weight=1)
        ttk.Label(cmd_frame, text="Command Preview:").grid(row=0, column=0, sticky="w")
        self.cmd_preview_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_frame, textvariable=self.cmd_preview_var, state="readonly", font="monospace 10")
        cmd_entry.grid(row=0, column=1, sticky="ew", padx=5)

        # --- Progress Bar ---
        self.progress_bar = ttk.Progressbar(self.master, mode='indeterminate', length=200)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 5))
        # Initially hidden, managed by start/stop scan

        # --- Output Area ---
        output_frame = ttk.Frame(self.master, padding="5")
        # Row index changed to 4 because progress bar is at 3
        output_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=5)
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=15, font="monospace 10")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_text.configure(state='disabled') # Make read-only initially

        # --- Control Buttons & Status ---
        control_frame = ttk.Frame(self.master, padding="5")
        # Row index changed to 5
        control_frame.grid(row=5, column=0, sticky="ew", padx=5, pady=5)
        control_frame.columnconfigure(4, weight=1) # Push status label to the right

        self.start_button = ttk.Button(control_frame, text="Start Scan", command=self.start_scan)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop Scan", command=self.stop_scan, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)

        self.clear_button = ttk.Button(control_frame, text="Clear Output", command=self.clear_output)
        self.clear_button.grid(row=0, column=2, padx=5)

        self.export_button = ttk.Button(control_frame, text="Export Output", command=self.export_results)
        self.export_button.grid(row=0, column=3, padx=5) # New Export Button

        self.status_label = ttk.Label(control_frame, text="Status: Idle", anchor="e")
        self.status_label.grid(row=0, column=4, sticky="e", padx=5)

        self.exit_button = ttk.Button(control_frame, text="Exit", command=self.master.quit)
        self.exit_button.grid(row=0, column=5, padx=5)

        # Initial setup for mode options visibility
        self.on_mode_change() # Call once to set initial visibility

    def create_common_options(self, parent):
        """Create widgets for common options tab."""
        ttk.Label(parent, text="Threads (-t):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.threads_var = tk.StringVar(value='10')
        self.threads_entry = ttk.Entry(parent, textvariable=self.threads_var, width=5)
        self.threads_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.threads_entry.bind("<KeyRelease>", self.update_command_preview)

        self.quiet_var = tk.BooleanVar()
        self.quiet_check = ttk.Checkbutton(parent, text="Quiet (-q)", variable=self.quiet_var, command=self.update_command_preview)
        self.quiet_check.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        self.no_progress_var = tk.BooleanVar(value=True)
        self.no_progress_check = ttk.Checkbutton(parent, text="No Progress (--no-progress)", variable=self.no_progress_var, command=self.update_command_preview)
        self.no_progress_check.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)

    def create_network_options(self, parent):
        """Create widgets for network options tab."""
        ttk.Label(parent, text="Proxy (--proxy):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.proxy_var = tk.StringVar()
        self.proxy_entry = ttk.Entry(parent, textvariable=self.proxy_var, width=30)
        self.proxy_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.proxy_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(parent, text="Timeout (--timeout):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.timeout_var = tk.StringVar(value='10s')
        self.timeout_entry = ttk.Entry(parent, textvariable=self.timeout_var, width=10)
        self.timeout_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.timeout_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(parent, text="User Agent (--useragent):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.useragent_var = tk.StringVar()
        self.useragent_entry = ttk.Entry(parent, textvariable=self.useragent_var, width=30)
        self.useragent_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        self.useragent_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(parent, text="Headers (-H):").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.headers_var = tk.StringVar()
        self.headers_entry = ttk.Entry(parent, textvariable=self.headers_var, width=30)
        self.headers_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        self.headers_entry.insert(0, 'Name:Value (one per line)') # Placeholder text
        self.headers_entry.bind("<KeyRelease>", self.update_command_preview)
        # Consider using a Text widget for multi-line headers if needed

    def create_dir_options(self, parent):
        """Create widgets for DIR mode options."""
        # Note: Parent is now the 'Mode Specific' tab frame
        self.dir_options_frame = ttk.Frame(parent, padding="5")
        # Grid placement handled by on_mode_change

        ttk.Label(self.dir_options_frame, text="Extensions (-x):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.ext_var = tk.StringVar()
        self.ext_entry = ttk.Entry(self.dir_options_frame, textvariable=self.ext_var, width=30)
        self.ext_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.ext_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(self.dir_options_frame, text="Include Codes (-s):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.status_var = tk.StringVar(value='200,204,301,302,307,401')
        self.status_entry = ttk.Entry(self.dir_options_frame, textvariable=self.status_var, width=30)
        self.status_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.status_entry.bind("<KeyRelease>", self.update_command_preview)

        ttk.Label(self.dir_options_frame, text="Exclude Codes (-b):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.blacklist_var = tk.StringVar(value='403,404')
        self.blacklist_entry = ttk.Entry(self.dir_options_frame, textvariable=self.blacklist_var, width=30)
        self.blacklist_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.blacklist_entry.bind("<KeyRelease>", self.update_command_preview)

        self.follow_redirect_var = tk.BooleanVar()
        self.follow_redirect_check = ttk.Checkbutton(self.dir_options_frame, text="Follow Redirects (--follow-redirect)", variable=self.follow_redirect_var, command=self.update_command_preview)
        self.follow_redirect_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        self.no_tls_var = tk.BooleanVar(value=True)
        self.no_tls_check = ttk.Checkbutton(self.dir_options_frame, text="Skip TLS Verify (-k)", variable=self.no_tls_var, command=self.update_command_preview)
        self.no_tls_check.grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=2)


    def create_dns_options(self, parent):
        """Create widgets for DNS mode options."""
        self.dns_options_frame = ttk.Frame(parent, padding="5")
        # Grid placement handled by on_mode_change

        self.show_cname_var = tk.BooleanVar()
        self.show_cname_check = ttk.Checkbutton(self.dns_options_frame, text="Show CNAMEs (-c)", variable=self.show_cname_var, command=self.update_command_preview)
        self.show_cname_check.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        self.show_ips_var = tk.BooleanVar()
        self.show_ips_check = ttk.Checkbutton(self.dns_options_frame, text="Show IPs (-i)", variable=self.show_ips_var, command=self.update_command_preview)
        self.show_ips_check.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        ttk.Label(self.dns_options_frame, text="Resolver (-r):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.resolver_var = tk.StringVar()
        self.resolver_entry = ttk.Entry(self.dns_options_frame, textvariable=self.resolver_var, width=30)
        self.resolver_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.resolver_entry.bind("<KeyRelease>", self.update_command_preview)

    def create_vhost_options(self, parent):
        """Create widgets for VHOST mode options."""
        self.vhost_options_frame = ttk.Frame(parent, padding="5")
        # Grid placement handled by on_mode_change

        self.vhost_follow_redirect_var = tk.BooleanVar()
        self.vhost_follow_redirect_check = ttk.Checkbutton(self.vhost_options_frame, text="Follow Redirects (--follow-redirect)", variable=self.vhost_follow_redirect_var, command=self.update_command_preview)
        self.vhost_follow_redirect_check.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        self.vhost_no_tls_var = tk.BooleanVar(value=True)
        self.vhost_no_tls_check = ttk.Checkbutton(self.vhost_options_frame, text="Skip TLS Verify (-k)", variable=self.vhost_no_tls_var, command=self.update_command_preview)
        self.vhost_no_tls_check.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        self.vhost_append_domain_var = tk.BooleanVar()
        self.vhost_append_domain_check = ttk.Checkbutton(self.vhost_options_frame, text="Append Domain (--append-domain)", variable=self.vhost_append_domain_var, command=self.update_command_preview)
        self.vhost_append_domain_check.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=2)


    def on_mode_change(self, event=None):
        """Handles showing/hiding options when the mode changes."""
        mode = self.current_mode.get()
        is_dir = (mode == 'Directory/File')
        is_dns = (mode == 'DNS Subdomain')
        is_vhost = (mode == 'Virtual Host')

        # Forget all mode-specific frames first
        self.dir_options_frame.grid_forget()
        self.dns_options_frame.grid_forget()
        self.vhost_options_frame.grid_forget()

        # Grid the correct frame back onto the mode-specific tab
        if is_dir:
            self.dir_options_frame.grid(row=0, column=0, sticky="nsew")
        elif is_dns:
            self.dns_options_frame.grid(row=0, column=0, sticky="nsew")
        elif is_vhost:
             self.vhost_options_frame.grid(row=0, column=0, sticky="nsew")

        # Ensure the parent tab resizes if needed (might not be necessary)
        self.tab_mode_specific.columnconfigure(0, weight=1)
        self.tab_mode_specific.rowconfigure(0, weight=1)

        self.update_command_preview() # Update preview after changing mode

    def browse_wordlist(self):
        """Opens a file dialog to select a wordlist."""
        filename = filedialog.askopenfilename(
            title="Select Wordlist",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filename:
            self.wordlist_entry.delete(0, tk.END)
            self.wordlist_entry.insert(0, filename)
            self.update_command_preview()

    def apply_coloring(self, line):
        """Applies syntax highlighting tags based on line content."""
        line = line.strip() # Work with stripped line for matching
        tags = () # Default: no tags

        # Simple status code coloring for DIR/VHOST modes
        match_status = re.match(r'.*\(Status: (\d{3})\)', line)
        if match_status:
            status_code = int(match_status.group(1))
            if status_code == 200: tags = ("status_200",)
            elif 300 <= status_code < 400: tags = ("status_30x",)
            elif status_code == 401: tags = ("status_401",)
            elif status_code == 403: tags = ("status_403",)
            elif 500 <= status_code < 600: tags = ("status_50x",)
            # Add more specific codes if needed

        # Coloring for DNS mode
        elif line.startswith("Found:"):
             tags = ("dns",)

        # Coloring for VHOST mode (similar to DIR, uses status codes)
        # (Already handled by status code logic above if format is the same)
        # Add specific VHOST tags if output differs significantly

        # Coloring for errors or info lines
        elif line.startswith("ERROR:") or "Error:" in line:
            tags = ("error",)
        elif line.startswith("---") or line.startswith("===") or line.startswith("[*]") or line.startswith("[+]"):
            tags = ("info",)

        return line + "\n", tags # Return original line + newline and tags


    def update_output(self):
        """Checks the output queue and updates the text area with coloring."""
        try:
            while True: # Process all messages currently in the queue
                line = self.output_queue.get_nowait()
                if line is None: # Sentinel found
                    self.set_scan_state(running=False, status="Finished")
                    self.progress_bar.stop()
                    self.progress_bar.grid_remove() # Hide progress bar
                    return # Stop checking queue for this cycle
                else:
                    self.output_text.configure(state='normal') # Enable writing
                    # Apply coloring
                    colored_line, tags = self.apply_coloring(line)
                    self.output_text.insert(tk.END, colored_line, tags)
                    self.output_text.see(tk.END) # Scroll to the end
                    self.output_text.configure(state='disabled') # Disable writing
        except queue.Empty:
            # If the thread is still alive, schedule another check
            if self.proc_thread and self.proc_thread.is_alive():
                self.master.after(100, self.update_output) # Check again in 100ms
            # If thread died unexpectedly without sentinel, update state
            elif self.stop_button['state'] == tk.NORMAL: # Check if we thought it was running
                 self.set_scan_state(running=False, status="Error/Unexpected Finish")
                 self.progress_bar.stop()
                 self.progress_bar.grid_remove()


    def build_command_list(self):
        """Builds the command list from GUI values. Returns list or raises ValueError."""
        target = self.target_entry.get().strip()
        wordlist = self.wordlist_entry.get().strip()
        mode_key = self.current_mode.get()
        mode_cmd = self.modes.get(mode_key)

        # Basic validation
        if not mode_cmd: raise ValueError("Invalid mode selected.")
        if not target: raise ValueError("Target URL/Domain cannot be empty.")
        if not wordlist: raise ValueError("Wordlist cannot be empty.")
        if not os.path.exists(wordlist): raise ValueError(f"Wordlist file not found: {wordlist}")
        if not GOBUSTER_CMD: raise ValueError("Gobuster command path not found.")

        command = [GOBUSTER_CMD, mode_cmd]

        # Mode-specific required args
        if mode_cmd in ['dir', 'vhost']:
            if not target.startswith(('http://', 'https://')):
                raise ValueError(f"Target for '{mode_cmd}' mode must start with http:// or https://")
            command.extend(['-u', target])
        elif mode_cmd == 'dns':
            if target.startswith(('http://', 'https://')):
                raise ValueError("Target for 'dns' mode should be a domain name (e.g., example.com), not a URL.")
            command.extend(['-d', target])

        # Common args
        command.extend(['-w', wordlist])
        try:
            threads = int(self.threads_var.get().strip())
            if threads <= 0: raise ValueError()
            command.extend(['-t', str(threads)])
        except ValueError:
            raise ValueError("Threads must be a positive integer.")

        if self.quiet_var.get(): command.append('-q')
        if self.no_progress_var.get(): command.append('--no-progress')

        # Network Tab Options
        if self.proxy_var.get(): command.extend(['--proxy', self.proxy_var.get().strip()])
        if self.timeout_var.get(): command.extend(['--timeout', self.timeout_var.get().strip()])
        if self.useragent_var.get(): command.extend(['--useragent', self.useragent_var.get().strip()])
        if self.headers_var.get() and self.headers_var.get() != 'Name:Value (one per line)':
             # Simple split by newline for headers, assumes correct user format
             headers = self.headers_var.get().strip().split('\n')
             for header in headers:
                 if header.strip(): # Ignore empty lines
                     command.extend(['-H', header.strip()])

        # Mode-specific optional args
        if mode_cmd == 'dir':
            if self.ext_var.get(): command.extend(['-x', self.ext_var.get().strip()])
            if self.status_var.get(): command.extend(['-s', self.status_var.get().strip()])
            if self.blacklist_var.get(): command.extend(['-b', self.blacklist_var.get().strip()])
            if self.follow_redirect_var.get(): command.append('--follow-redirect')
            if self.no_tls_var.get(): command.append('-k')
        elif mode_cmd == 'dns':
            if self.show_cname_var.get(): command.append('-c')
            if self.show_ips_var.get(): command.append('-i')
            if self.resolver_var.get(): command.extend(['-r', self.resolver_var.get().strip()])
        elif mode_cmd == 'vhost':
             if self.vhost_follow_redirect_var.get(): command.append('--follow-redirect')
             if self.vhost_no_tls_var.get(): command.append('-k')
             if self.vhost_append_domain_var.get(): command.append('--append-domain')

        return command

    def update_command_preview(self, event=None):
        """Updates the command preview text field."""
        try:
            cmd_list = self.build_command_list()
            preview_text = " ".join(map(shlex.quote, cmd_list))
            self.cmd_preview_var.set(preview_text)
        except ValueError as e:
            self.cmd_preview_var.set(f"Error: {e}")
        except Exception as e:
             self.cmd_preview_var.set(f"Error building preview: {e}")


    def set_scan_state(self, running: bool, status: str):
        """Updates the GUI state (buttons, status label, progress bar)."""
        self.start_button.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL if running else tk.DISABLED)
        self.status_label.config(text=f"Status: {status}")
        if running:
            self.progress_bar.grid() # Show progress bar
            self.progress_bar.start(10) # Start indeterminate animation (interval in ms)
        else:
            self.progress_bar.stop()
            self.progress_bar.grid_remove() # Hide progress bar

    def start_scan(self):
        """Starts the gobuster scan in a thread."""
        if self.proc_thread and self.proc_thread.is_alive():
            messagebox.showwarning("Scan Active", "A scan is already running.")
            return

        try:
            args_list = self.build_command_list()
            self.output_text.configure(state='normal')
            self.output_text.delete('1.0', tk.END) # Clear previous output
            self.output_text.insert(tk.END, f"Starting Gobuster: {' '.join(map(shlex.quote, args_list))}\n\n", ("info",)) # Use info tag
            self.output_text.configure(state='disabled')
            self.set_scan_state(running=True, status="Running...")

            # Reset stop event and clear queues
            self.stop_event.clear()
            while not self.output_queue.empty(): self.output_queue.get()
            while not self.process_queue.empty(): self.process_queue.get()

            # Start thread
            self.proc_thread = threading.Thread(
                target=run_gobuster,
                args=(args_list, self.output_queue, self.process_queue, self.stop_event),
                daemon=True
            )
            self.proc_thread.start()

            # Start polling the output queue
            self.master.after(100, self.update_output)

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            self.set_scan_state(running=False, status="Input Error")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Gobuster:\n{e}")
            self.set_scan_state(running=False, status="Error")

    def stop_scan(self):
        """Signals the gobuster thread/process to stop."""
        self.set_scan_state(running=False, status="Stopping...") # Update GUI immediately
        self.stop_event.set() # Signal the thread to stop reading output

        # Attempt to terminate the process directly
        proc_to_stop = None
        try:
            # Peek or get from queue without blocking indefinitely if possible
            # Using get_nowait is reasonable here
            proc_to_stop = self.process_queue.get_nowait()
        except queue.Empty:
            self.insert_output_line("\n--- Stop requested, but process not found in queue ---", ("info",))
        except Exception as e:
             self.insert_output_line(f"\n--- Error getting process from queue for stop: {e} ---", ("error",))

        if proc_to_stop and proc_to_stop.poll() is None: # Check if it's running
            self.insert_output_line("\n--- Sending terminate signal to Gobuster ---", ("info",))
            try:
                proc_to_stop.terminate()
                try:
                    proc_to_stop.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                     self.insert_output_line("\n--- Process did not terminate quickly, sending kill signal ---", ("error",))
                     proc_to_stop.kill()
            except Exception as e:
                 self.insert_output_line(f"\n--- Error trying to stop process: {e} ---", ("error",))

        # Final state update after attempting stop
        # The update_output loop will handle the final state update when it sees the sentinel or thread ends
        # We just ensure buttons are reset here in case the thread hangs briefly
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Stopped by user")
        self.progress_bar.stop()
        self.progress_bar.grid_remove()


    def insert_output_line(self, line, tags=()):
        """Helper to insert a line into the output text widget safely."""
        try:
            self.output_text.configure(state='normal')
            self.output_text.insert(tk.END, line, tags)
            self.output_text.see(tk.END)
            self.output_text.configure(state='disabled')
        except tk.TclError:
            # Handle cases where the window might be closing
            print("Warning: Could not write to output widget (likely closing).")
        except Exception as e:
            print(f"Error inserting output line: {e}")


    def clear_output(self):
        """Clears the output text area."""
        self.output_text.configure(state='normal')
        self.output_text.delete('1.0', tk.END)
        self.output_text.configure(state='disabled')

    def export_results(self):
        """Saves the content of the output area to a file."""
        output_content = self.output_text.get("1.0", tk.END).strip() # Get all text
        if not output_content:
            messagebox.showwarning("Export Empty", "There is no output to export.")
            return

        filepath = filedialog.asksaveasfilename(
            title="Save Gobuster Output",
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )

        if filepath: # User selected a file (didn't cancel)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(output_content)
                messagebox.showinfo("Export Successful", f"Output saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to save file:\n{e}")


# --- Main Execution ---
if __name__ == '__main__':
    # Check for tkinter availability early
    try:
        root = tk.Tk()
        root.withdraw() # Hide the default empty window immediately
    except tk.TclError:
        print("ERROR: Tkinter is not available or configured correctly.", file=sys.stderr)
        print("On Debian/Ubuntu/Kali, try: sudo apt update && sudo apt install python3-tk", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred initializing Tkinter: {e}", file=sys.stderr)
        sys.exit(1)

    # Now that Tkinter is confirmed, run the app
    root.deiconify() # Show the window we created
    app = GobusterApp(root)
    root.mainloop()
