#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import threading
import queue
import os
import shlex
import shutil
import sys
import re
import platform
import datetime

import config
import ui_gobuster
import ui_nmap
import ui_sqlmap
import ui_nikto
import ui_john

FOUND_EXECUTABLES = {}

def find_executable(tool_name):
    print(f"\n[DEBUG] Attempting to find executable for tool: {tool_name}")
    if tool_name in FOUND_EXECUTABLES and FOUND_EXECUTABLES[tool_name]:
        print(f"[DEBUG] Found '{tool_name}' in cache: {FOUND_EXECUTABLES[tool_name]}")
        return FOUND_EXECUTABLES[tool_name]

    paths_to_check = config.EXECUTABLE_PATHS.get(tool_name, [tool_name])
    print(f"[DEBUG] Paths to check for '{tool_name}': {paths_to_check}")
    for path_candidate in paths_to_check:
        print(f"[DEBUG] Checking candidate for '{tool_name}': '{path_candidate}'")
        if path_candidate == tool_name:
             print(f"[DEBUG] Python's PATH environment variable: {os.environ.get('PATH')}")
        
        found_path = shutil.which(path_candidate)
        print(f"[DEBUG] shutil.which('{path_candidate}') returned: '{found_path}'")
        
        if found_path:
            is_executable = os.access(found_path, os.X_OK)
            print(f"[DEBUG] Path '{found_path}' for '{tool_name}' exists. Is executable by script: {is_executable}")
            if not is_executable:
                print(f"[DEBUG] Path '{found_path}' is NOT marked as executable by the current user/script. Skipping.")
                continue

            if tool_name == 'sqlmap' and (found_path.endswith('.py') or 'sqlmap.py' in path_candidate):
                python_exe = shutil.which('python3') or shutil.which('python')
                if python_exe:
                    print(f"[DEBUG] '{tool_name}' is a python script, {python_exe} found.")
                    FOUND_EXECUTABLES[tool_name] = [python_exe, found_path]
                    return FOUND_EXECUTABLES[tool_name]
                else:
                    print(f"[DEBUG] '{tool_name}' is a python script, but no python/python3 interpreter NOT found.")
                    continue 
            elif tool_name == 'nikto' and (found_path.endswith('.pl') or 'nikto.pl' in path_candidate):
                perl_exe = shutil.which('perl')
                if perl_exe:
                    print(f"[DEBUG] '{tool_name}' is a perl script, perl found.")
                    FOUND_EXECUTABLES[tool_name] = [perl_exe, found_path]
                    return FOUND_EXECUTABLES[tool_name]
                else:
                    print(f"[DEBUG] '{tool_name}' is a perl script, but perl interpreter NOT found.")
                    continue
            
            FOUND_EXECUTABLES[tool_name] = [found_path]
            print(f"[DEBUG] Successfully found and cached '{tool_name}' as: {FOUND_EXECUTABLES[tool_name]}")
            return FOUND_EXECUTABLES[tool_name]
            
    FOUND_EXECUTABLES[tool_name] = None
    print(f"[DEBUG] Failed to find '{tool_name}' after checking all candidates. Caching as None.")
    return None

for tool_key in config.EXECUTABLE_PATHS.keys():
    find_executable(tool_key)

def run_command_in_thread(args_list, output_queue, process_queue, stop_event, tool_name="Tool"):
    process = None
    try:
        process = subprocess.Popen(
            args_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            errors='replace'
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
        output_queue.put(f"Please ensure {tool_name} is installed and in your PATH or adjust EXECUTABLE_PATHS in config.py.")
    except Exception as e:
        output_queue.put(f"\n--- An error occurred during {tool_name} execution: {type(e).__name__}: {e} ---")
    finally:
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.5)
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=0.5)
            except Exception as e:
                print(f"Error during final {tool_name} process cleanup: {e}", file=sys.stderr)
                try:
                    output_queue.put(f"\n--- Error during final {tool_name} process cleanup: {e} ---")
                except Exception:
                    pass
        output_queue.put(None) 
        process_queue.put(None)

class PentestApp:
    def __init__(self, master):
        self.master = master
        master.title("Redboar Pentesting GUI")
        master.geometry("1000x800")
        master.minsize(850, 700)

        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        if 'clam' in available_themes: self.style.theme_use('clam')
        elif 'alt' in available_themes: self.style.theme_use('alt')

        self.process = None
        self.proc_thread = None
        self.output_queue = queue.Queue()
        self.process_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.proc_thread_tool_name = "Tool"

        self.current_tool_name = tk.StringVar(value="Gobuster")

        self._create_menubar()
        self.create_widgets()
        self.update_command_preview()
        self.on_tool_selected()

        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=0) 
        master.rowconfigure(1, weight=0) 
        master.rowconfigure(2, weight=0) 
        master.rowconfigure(3, weight=1) 
        master.rowconfigure(4, weight=0) 

        self._configure_output_tags()

        self.tool_ui_builders = {
            "Gobuster": ui_gobuster,
            "Nmap": ui_nmap,
            "SQLMap": ui_sqlmap,
            "Nikto": ui_nikto,
            "John the Ripper": ui_john
        }


    def _create_menubar(self):
        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)

        help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About Redboar", command=self.show_about_dialog)

    def show_about_dialog(self):
        about_message = (
            "Redboar Pentesting GUI\n\n"
            "Version: 0.3 (Refactored)\n"
            f"Date: {datetime.date.today().strftime('%Y-%m-%d')}\n\n"
            "A GUI wrapper for common pentesting tools.\n"
            "Remember to use these tools responsibly and ethically."
        )
        messagebox.showinfo("About Redboar", about_message)

    def _configure_output_tags(self):
        self.output_text.tag_configure("status_200", foreground="green")
        self.output_text.tag_configure("status_30x", foreground="blue")
        self.output_text.tag_configure("status_401", foreground="darkorange")
        self.output_text.tag_configure("status_403", foreground="red")
        self.output_text.tag_configure("status_50x", foreground="magenta")
        self.output_text.tag_configure("error", foreground="red", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("info", foreground="grey")
        self.output_text.tag_configure("success", foreground="green", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("nmap_port_open", foreground="green")
        self.output_text.tag_configure("nmap_port_closed", foreground="red")
        self.output_text.tag_configure("nmap_port_filtered", foreground="orange")
        self.output_text.tag_configure("nmap_host_up", foreground="green")
        self.output_text.tag_configure("nmap_service", foreground="blue")
        self.output_text.tag_configure("sqlmap_vulnerable", foreground="red", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("sqlmap_info", foreground="cyan")
        self.output_text.tag_configure("sqlmap_dbms", foreground="purple")
        self.output_text.tag_configure("sqlmap_data", foreground="green")
        self.output_text.tag_configure("nikto_vuln", foreground="red", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("nikto_info", foreground="blue")
        self.output_text.tag_configure("nikto_server", foreground="purple")
        self.output_text.tag_configure("john_cracked", foreground="green", font=('monospace', 10, 'bold'))
        self.output_text.tag_configure("john_status", foreground="grey")
        self.output_text.tag_configure("tool_not_found_msg", foreground="red", font=('monospace', 10, 'italic'))

    def create_widgets(self):
        self.main_notebook = ttk.Notebook(self.master, padding="5")
        self.main_notebook.grid(row=0, column=0, columnspan=2, sticky="new", padx=5, pady=5)
        self.main_notebook.bind("<<NotebookTabChanged>>", self.on_tool_selected)

        self.tool_frames = {}
        tool_tabs_config = [
            ("Gobuster", ui_gobuster.create_ui),
            ("Nmap", ui_nmap.create_ui),
            ("SQLMap", ui_sqlmap.create_ui),
            ("Nikto", ui_nikto.create_ui),
            ("John the Ripper", ui_john.create_ui)
        ]

        for name, creation_method in tool_tabs_config:
            frame = ttk.Frame(self.main_notebook, padding="10")
            self.main_notebook.add(frame, text=f' {name} ')
            self.tool_frames[name] = frame
            creation_method(frame, self)
            
            not_found_label = ttk.Label(frame, text=f"{name} executable not found. Please install it or check your PATH.", style="tool_not_found_msg.TLabel")
            setattr(self, f"{name.lower().replace(' ', '_').replace('-', '_')}_not_found_label", not_found_label)

        cmd_preview_frame = ttk.Frame(self.master, padding="5 0")
        cmd_preview_frame.grid(row=1, column=0, sticky="ew", padx=5)
        cmd_preview_frame.columnconfigure(1, weight=1)
        
        ttk.Label(cmd_preview_frame, text="Command Preview:").grid(row=0, column=0, sticky="w", padx=(0,5))
        self.cmd_preview_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_preview_frame, textvariable=self.cmd_preview_var, state="readonly", font="monospace 10")
        cmd_entry.grid(row=0, column=1, sticky="ew")
        
        self.copy_cmd_button = ttk.Button(cmd_preview_frame, text="Copy", command=self.copy_command_to_clipboard, width=8)
        self.copy_cmd_button.grid(row=0, column=2, sticky="e", padx=(5,0))

        self.progress_bar = ttk.Progressbar(self.master, mode='indeterminate', length=200)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=(5, 5))
        self.progress_bar.grid_remove()

        output_frame = ttk.Frame(self.master, padding="5")
        output_frame.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=15, font="monospace 10")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_text.configure(state='disabled')

        control_frame = ttk.Frame(self.master, padding="10 5")
        control_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=5)
        control_frame.columnconfigure(4, weight=1)

        self.start_button = ttk.Button(control_frame, text="Start Scan", command=self.start_scan, width=12)
        self.start_button.grid(row=0, column=0, padx=5)
        self.stop_button = ttk.Button(control_frame, text="Stop Scan", command=self.stop_scan, state=tk.DISABLED, width=12)
        self.stop_button.grid(row=0, column=1, padx=5)
        self.clear_button = ttk.Button(control_frame, text="Clear Output", command=self.clear_output, width=12)
        self.clear_button.grid(row=0, column=2, padx=5)
        self.export_button = ttk.Button(control_frame, text="Export Output", command=self.export_results, width=12)
        self.export_button.grid(row=0, column=3, padx=5)
        self.status_label = ttk.Label(control_frame, text="Status: Idle", anchor="e")
        self.status_label.grid(row=0, column=4, sticky="e", padx=5)

    def copy_command_to_clipboard(self):
        command = self.cmd_preview_var.get()
        if command and not command.startswith("Error:"):
            self.master.clipboard_clear()
            self.master.clipboard_append(command)
            self.status_label.config(text="Status: Command copied to clipboard!")
            self.master.after(2000, lambda: self.status_label.config(text=f"Status: Idle" if self.stop_button['state'] == tk.DISABLED else self.status_label.cget("text")))
        elif command.startswith("Error:"):
             messagebox.showwarning("Copy Error", "Cannot copy an error message from command preview.")
        else:
            messagebox.showinfo("Copy Info", "No command to copy.")

    def on_tool_selected(self, event=None):
        try:
            selected_tab_index = self.main_notebook.index(self.main_notebook.select())
            tool_name_display = self.main_notebook.tab(selected_tab_index, "text").strip()
        except tk.TclError:
            tool_name_display = self.current_tool_name.get()
            
        self.current_tool_name.set(tool_name_display)
        self.update_command_preview()

        tool_key_attr = tool_name_display.lower().replace(' ', '_').replace('-', '_')
        not_found_label_attr = f"{tool_key_attr}_not_found_label"
        
        for tool_frame_name_iter in self.tool_frames.keys():
            key_iter = tool_frame_name_iter.lower().replace(' ', '_').replace('-', '_')
            label_attr_name_iter = f"{key_iter}_not_found_label"
            if hasattr(self, label_attr_name_iter):
                getattr(self, label_attr_name_iter).grid_remove()

        tool_executable_key = tool_name_display.lower().replace(" ", "")
        if tool_executable_key == "johntheripper": tool_executable_key = "john"

        if not FOUND_EXECUTABLES.get(tool_executable_key):
            self.start_button.config(state=tk.DISABLED)
            if hasattr(self, not_found_label_attr):
                getattr(self, not_found_label_attr).grid(row=0, column=0, columnspan=3, sticky="new", pady=(0,10), padx=5)
            self.status_label.config(text=f"Status: {tool_name_display} not found.")
        else:
            if not (self.proc_thread and self.proc_thread.is_alive()):
                self.start_button.config(state=tk.NORMAL)
                self.status_label.config(text="Status: Idle")
            if hasattr(self, not_found_label_attr):
                getattr(self, not_found_label_attr).grid_remove()

    def browse_file(self, string_var_to_set, title="Select File"):
        filename = filedialog.askopenfilename(title=title)
        if filename:
            string_var_to_set.set(filename)
            self.update_command_preview()

    def apply_coloring(self, line_with_newline):
        line = line_with_newline.strip()
        tags = ()
        tool = self.current_tool_name.get()

        if "ERROR:" in line or "Error:" in line or "[Errno" in line or "[CRITICAL]" in line or "critical error" in line.lower():
            tags = ("error",)
        elif "Failed" in line and not "Failed login" in line:
             tags = ("error",)
        elif line.startswith("---") or line.startswith("===") or line.startswith("[*]") or line.startswith("[+]") or "[INFO]" in line or "[DEBUG]" in line or "[VERBOSE]" in line:
            tags = ("info",)

        if tool == "Gobuster":
            match_status = re.search(r'\(Status: (\d{3})\)', line)
            if match_status:
                status_code = int(match_status.group(1))
                if status_code == 200: tags = ("status_200",)
                elif 300 <= status_code < 400: tags = ("status_30x",)
                elif status_code == 401: tags = ("status_401",)
                elif status_code == 403: tags = ("status_403",)
                elif 500 <= status_code < 600: tags = ("status_50x",)
            elif line.startswith("Found:"): tags = ("success",)
        elif tool == "Nmap":
            if "Host is up" in line: tags = ("nmap_host_up", "info")
            elif "/open" in line and "//" not in line : tags = ("nmap_port_open",)
            elif "/closed" in line and "://" not in line: tags = ("nmap_port_closed",)
            elif "/filtered" in line and "://" not in line : tags = ("nmap_port_filtered",)
            if "Service Info:" in line or "OS details:" in line or "MAC Address:" in line: tags = ("nmap_service", "info")
        elif tool == "SQLMap":
            if "vulnerable" in line.lower() and "not vulnerable" not in line.lower(): tags = ("sqlmap_vulnerable",)
            if "fetched data" in line.lower() or (line.startswith("[") and line.endswith("]") and ":" not in line) or ("|" in line and "banner" not in line.lower()): tags = ("sqlmap_data",)
            if "DBMS" in line and ":" in line: tags =("sqlmap_dbms",)
            if "[INFO]" in line or "[DEBUG]" in line or "[WARNING]" in line: tags = ("sqlmap_info",) 
        elif tool == "Nikto":
            if line.startswith("+") and ("OSVDB" in line or "vulnerability" in line.lower() or "CVE-" in line): tags = ("nikto_vuln",)
            elif line.startswith("+ Server:"): tags =("nikto_server",)
            elif line.startswith("+"): tags = ("nikto_info",)
        elif tool == "John the Ripper":
            if not line.startswith("Loaded") and \
               not line.startswith("Proceeding") and \
               not line.startswith("Using default") and \
               not line.startswith("Warning:") and \
               not line.startswith("Note:") and \
               not line.startswith("Press 'q'") and \
               not "words:" in line and \
               not "guesses:" in line and \
               not "g/s" in line and \
               not re.match(r'^\d+g \d+:\d+:\d+:\d+.*', line) and \
               re.search(r'^\S+\s+\(?[^)]+\)?\s*$', line):
                tags = ("john_cracked",)
            elif "guesses:" in line or "Proceeding with" in line or "Loaded" in line or "Remaining" in line or "words:" in line or "g/s" in line:
                tags = ("john_status",)
            elif "No passwords" in line or "No password" in line : tags = ("info",)

        return line_with_newline, tags

    def update_output(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line is None:
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
            elif self.stop_button['state'] == tk.NORMAL:
                self.set_scan_state(running=False, status="Error/Unexpected Finish")

    def _get_command_for_current_tool(self):
        tool_name_display = self.current_tool_name.get()
        tool_name_key = tool_name_display.lower().replace(" ", "")
        if tool_name_key == "johntheripper": tool_name_key = "john"
        
        base_executable_cmd = FOUND_EXECUTABLES.get(tool_name_key)
        if not base_executable_cmd:
            raise ValueError(f"{tool_name_display} executable not found.")
        
        cmd_list = list(base_executable_cmd)
        
        tool_module = self.tool_ui_builders.get(tool_name_display)
        if tool_module and hasattr(tool_module, 'build_command'):
            tool_specific_args = tool_module.build_command(self)
            cmd_list.extend(tool_specific_args)
        else:
            raise ValueError(f"Command builder not found for {tool_name_display}")
            
        return cmd_list

    def update_command_preview(self, event=None):
        try:
            cmd_list = self._get_command_for_current_tool()
            quoted_cmd_list = [shlex.quote(str(item)) for item in cmd_list]
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

        current_tool_display_name = self.current_tool_name.get()
        current_tool_key = current_tool_display_name.lower().replace(" ", "")
        if current_tool_key == "johntheripper": current_tool_key = "john"
        
        if not FOUND_EXECUTABLES.get(current_tool_key):
             messagebox.showerror("Tool Not Found", f"{current_tool_display_name} executable not found. Cannot start scan.")
             self.start_button.config(state=tk.DISABLED)
             return

        try:
            args_list = self._get_command_for_current_tool()
            self.output_text.configure(state='normal')
            self.output_text.delete('1.0', tk.END)
            cmd_display_for_log = " ".join(map(str, args_list))
            self.output_text.insert(tk.END, f"Starting {current_tool_display_name}: {cmd_display_for_log}\n\n", ("info",))
            self.output_text.configure(state='disabled')
            self.set_scan_state(running=True, status=f"Running {current_tool_display_name}...")

            self.stop_event.clear()
            while not self.output_queue.empty(): self.output_queue.get_nowait()
            while not self.process_queue.empty(): self.process_queue.get_nowait()

            self.proc_thread_tool_name = current_tool_display_name
            self.proc_thread = threading.Thread(
                target=run_command_in_thread,
                args=(args_list, self.output_queue, self.process_queue, self.stop_event, current_tool_display_name),
                daemon=True
            )
            self.proc_thread.start()
            self.master.after(100, self.update_output)

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            self.set_scan_state(running=False, status="Input Error")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start {current_tool_display_name}:\n{type(e).__name__}: {e}")
            self.set_scan_state(running=False, status="Error")

    def stop_scan(self):
        tool_name = self.proc_thread_tool_name if hasattr(self, 'proc_thread_tool_name') and self.proc_thread_tool_name else "Scan"
        
        if not (self.proc_thread and self.proc_thread.is_alive()):
            self.set_scan_state(running=False, status=f"{tool_name} not running or already stopped.")
            return

        self.set_scan_state(running=False, status=f"Stopping {tool_name}...")
        self.stop_event.set()

        proc_to_stop = None
        try:
            proc_to_stop = self.process_queue.get(timeout=1)
        except queue.Empty:
            self.insert_output_line(f"\n--- Stop requested, but {tool_name} process object not found in queue after timeout. ---", ("info",))
        except Exception as e:
             self.insert_output_line(f"\n--- Error getting {tool_name} process from queue for stop: {e} ---", ("error",))

        if proc_to_stop and proc_to_stop.poll() is None:
            self.insert_output_line(f"\n--- Sending terminate signal to {tool_name} (PID: {proc_to_stop.pid}) ---", ("info",))
            try:
                proc_to_stop.terminate()
                try:
                    proc_to_stop.wait(timeout=1) 
                except subprocess.TimeoutExpired:
                     self.insert_output_line(f"\n--- {tool_name} process did not terminate quickly, sending kill signal ---", ("error",))
                     proc_to_stop.kill()
                     try:
                        proc_to_stop.wait(timeout=1) 
                     except subprocess.TimeoutExpired:
                        self.insert_output_line(f"\n--- {tool_name} process did not die after kill signal. ---", ("error",))
            except Exception as e:
                 self.insert_output_line(f"\n--- Error trying to stop {tool_name} process: {e} ---", ("error",))
        elif proc_to_stop and proc_to_stop.poll() is not None:
            self.insert_output_line(f"\n--- {tool_name} process already terminated (exit code: {proc_to_stop.poll()}). ---", ("info",))

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        if self.status_label.cget("text").endswith("..."):
            self.status_label.config(text=f"Status: {tool_name} stopped by user")
        self.progress_bar.stop()
        self.progress_bar.grid_remove()

    def insert_output_line(self, line, tags=()):
        try:
            self.output_text.configure(state='normal')
            self.output_text.insert(tk.END, line + "\n", tags)
            self.output_text.see(tk.END)
            self.output_text.configure(state='disabled')
        except tk.TclError:
            pass
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

def display_tool_installation_guidance(missing_tool_info):
    title = "Missing Tools - Installation Guidance"
    message = "The following tools could not be found automatically:\n\n"
    is_linux_apt = sys.platform.startswith('linux') and shutil.which('apt')

    for tool_key, display_name in missing_tool_info:
        message += f"- {display_name}\n"
        pkg_name = config.COMMON_PACKAGE_NAMES.get(tool_key)
        if is_linux_apt and pkg_name:
            message += f"  On Debian/Ubuntu, try: sudo apt update && sudo apt install -y {pkg_name}\n"
        elif tool_key == "sqlmap":
            message += f"  Consider cloning from GitHub: git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git sqlmap-dev\n"
            message += f"  Then run 'python3 sqlmap.py' from its directory.\n"
        elif tool_key == "nikto":
             message += f"  Consider cloning from GitHub: git clone https://github.com/sullo/nikto.git\n"
             message += f"  Then run 'perl nikto.pl' from its program/ directory.\n"
        else:
            message += f"  Please install it using your system's package manager or download it from its official website.\n"
        message += "\n"

    message += "\nFunctionality for these tools will be unavailable or may fail until they are installed and accessible in your system PATH, or their paths are configured in config.py (by editing EXECUTABLE_PATHS)."
    messagebox.showwarning(title, message)

if __name__ == '__main__':
    try:
        root = tk.Tk()
        root.withdraw() 
    except tk.TclError:
        print("ERROR: Tkinter is not available or configured correctly.", file=sys.stderr)
        print("On Debian/Ubuntu/Kali, try: sudo apt update && sudo apt install python3-tk", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred initializing Tkinter: {e}", file=sys.stderr)
        sys.exit(1)

    missing_tool_details = []
    
    for tool_key in config.EXECUTABLE_PATHS.keys():
        display_name = config.TOOL_DISPLAY_NAMES_MAP.get(tool_key, tool_key.capitalize())
        if not FOUND_EXECUTABLES.get(tool_key):
             missing_tool_details.append((tool_key, display_name))
    
    if missing_tool_details:
        display_tool_installation_guidance(missing_tool_details)

    root.deiconify()
    app = PentestApp(root)
    root.mainloop()
