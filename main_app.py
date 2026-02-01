#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import subprocess
import threading
import queue
import os
import shlex
import shutil
import sys
import re
import datetime
import logging
import signal
import json

from pathlib import Path
from shutil import which
import math

from core import config
from ui import ui_gobuster
from ui import ui_nmap
from ui import ui_sqlmap
from ui import ui_nikto
from ui import ui_john
from ui import ui_targets
from ui import ui_graph
from ui import ai_ui

from core import state_manager
from core import parsers

FOUND_EXECUTABLES = {}

# Configure logging (DEBUG when REDBOAR_DEBUG is set, otherwise INFO)
_log_level = logging.DEBUG if os.environ.get('REDBOAR_DEBUG') else logging.INFO
logging.basicConfig(level=_log_level, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("redboar")


def _normalize_tool_key(display_name: str) -> str:
    key = display_name.lower().replace(" ", "").replace("-", "")
    return "john" if key == "johntheripper" else key

def find_executable(tool_name):
    logger.debug("Attempting to find executable for tool: %s", tool_name)
    if tool_name in FOUND_EXECUTABLES and FOUND_EXECUTABLES[tool_name]:
        logger.debug("Found '%s' in cache: %s", tool_name, FOUND_EXECUTABLES[tool_name])
        return FOUND_EXECUTABLES[tool_name]

    paths_to_check = config.EXECUTABLE_PATHS.get(tool_name, [tool_name])
    logger.debug("Paths to check for '%s': %s", tool_name, paths_to_check)
    for path_candidate in paths_to_check:
        logger.debug("Checking candidate for '%s': '%s'", tool_name, path_candidate)
        if path_candidate == tool_name:
            logger.debug("Python PATH: %s", os.environ.get('PATH'))

        found_path = shutil.which(path_candidate)
        if not found_path and (os.path.isabs(path_candidate) or os.sep in path_candidate):
            if os.path.exists(path_candidate):
                found_path = os.path.abspath(path_candidate)
                logger.debug("Found '%s' by direct path: '%s'", tool_name, found_path)
        logger.debug("Candidate resolved to: '%s'", found_path)

        if found_path:
            if tool_name == 'sqlmap' and (found_path.endswith('.py') or 'sqlmap.py' in path_candidate):
                python_exe = shutil.which('python3') or shutil.which('python')
                if python_exe:
                    FOUND_EXECUTABLES[tool_name] = [python_exe, found_path]
                    logger.debug("'%s' is a python script, interpreter '%s' will be used", tool_name, python_exe)
                    return FOUND_EXECUTABLES[tool_name]
                else:
                    logger.debug("'%s' is a python script, but no python/python3 interpreter found.")
                    continue
            elif tool_name == 'nikto' and (found_path.endswith('.pl') or 'nikto.pl' in path_candidate):
                perl_exe = shutil.which('perl')
                if perl_exe:
                    FOUND_EXECUTABLES[tool_name] = [perl_exe, found_path]
                    logger.debug("'%s' is a perl script, interpreter '%s' will be used", tool_name, perl_exe)
                    return FOUND_EXECUTABLES[tool_name]
                else:
                    logger.debug("'%s' is a perl script, but perl interpreter not found.")
                    continue
            elif os.access(found_path, os.X_OK):
                FOUND_EXECUTABLES[tool_name] = [found_path]
                logger.debug("Successfully found and cached '%s' as: %s", tool_name, FOUND_EXECUTABLES[tool_name])
                return FOUND_EXECUTABLES[tool_name]
            else:
                logger.debug("Path '%s' is not executable and no interpreter was matched. Skipping.", found_path)

    FOUND_EXECUTABLES[tool_name] = None
    logger.debug("Failed to find '%s' after checking all candidates. Caching as None.")
    return None

for tool_key in config.EXECUTABLE_PATHS.keys():
    find_executable(tool_key)

def run_command_in_thread(args_list, output_queue, process_queue, stop_event, tool_name="Tool"):
    process = None
    try:
        popen_kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            errors='replace'
        )
        # On Linux, start a new process group so we can signal the whole tree on stop
        if os.name == 'posix' and hasattr(os, 'setsid'):
            popen_kwargs['preexec_fn'] = os.setsid
        process = subprocess.Popen(args_list, **popen_kwargs)
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
                if os.name == 'posix':
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    except Exception:
                        process.terminate()
                else:
                    process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    if os.name == 'posix':
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except Exception:
                            process.kill()
                    else:
                        process.kill()
                    process.wait(timeout=0.5)
            except Exception as e:
                logger.error("Error during final %s process cleanup: %s", tool_name, e)
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
        
        # Initialize State Manager
        self.state_manager = state_manager.StateManager()
        # Default project (or load last used if implemented later)
        if not self.state_manager.current_project_id:
             # Ensure a default exists or prompt. For now, let's create a default if none.
             # Actually, better to let user create one, but for usability we can have a 'Scratchpad' project potentially.
             # For simplicity phase 1: Just ensure user knows.
             pass

        # App icon (same logo as README). Keep a reference to avoid GC
        try:
            self._icon_image = tk.PhotoImage(file="icon.png")
            self.master.iconphoto(True, self._icon_image)
            # Create a smaller display version for header to avoid huge layouts
            try:
                w, h = self._icon_image.width(), self._icon_image.height()
                scale = max(1, int(max(w / 64, h / 64)))
                self._logo_display_image = self._icon_image.subsample(scale, scale)
            except Exception:
                self._logo_display_image = self._icon_image
        except Exception:
            pass

        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        if 'clam' in available_themes: self.style.theme_use('clam')
        elif 'alt' in available_themes: self.style.theme_use('alt')
        # Style for missing-tool labels
        self.style.configure("tool_not_found_msg.TLabel", foreground="red", font=("TkDefaultFont", 10, "italic"))
        self.style.configure("section.TLabelframe.Label", font=("TkDefaultFont", 10, "bold"))
        self.style.configure("Heading.TLabel", font=("TkDefaultFont", 10, "bold"))
        self.style.configure("AppTitle.TLabel", font=("TkDefaultFont", 16, "bold"))

        # Theme state
        self.current_theme_name = tk.StringVar(value="Neubrutalist")
        self._apply_theme(self.current_theme_name.get())

        self.proc_thread = None
        self.output_queue = queue.Queue()
        self.process_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.proc_thread_tool_name = "Tool"

        self.current_tool_name = tk.StringVar(value="Gobuster")
        self.extra_args_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self._last_search_index = None

        self._create_menubar()
        self.create_widgets()
        self.update_command_preview()
        self.on_tool_selected()

        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=0)  # header
        master.rowconfigure(1, weight=0)  # tabs
        master.rowconfigure(2, weight=0)  # command
        master.rowconfigure(3, weight=0)  # progress
        master.rowconfigure(4, weight=1)  # output
        master.rowconfigure(5, weight=0)  # controls

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

        project_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Project", menu=project_menu)
        project_menu.add_command(label="New Project...", command=self.new_project_dialog)
        project_menu.add_command(label="Open Project...", command=self.open_project_dialog)
        project_menu.add_separator()
        project_menu.add_command(label="Current Project Info", command=self.show_project_info)

        view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="View", menu=view_menu)
        for theme_name in ("Glass", "Brutalist", "Neubrutalist"):
            view_menu.add_radiobutton(
                label=theme_name,
                variable=self.current_theme_name,
                value=theme_name,
                command=lambda: self._apply_theme(self.current_theme_name.get())
            )

        profiles_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Profiles", menu=profiles_menu)
        profiles_menu.add_command(label="Save Profile...", command=self.save_profile)
        profiles_menu.add_command(label="Load Profile...", command=self.load_profile)

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
        fixed_bold = ("TkFixedFont", 10, "bold")
        self.output_text.tag_configure("status_200", foreground="green")
        self.output_text.tag_configure("status_30x", foreground="blue")
        self.output_text.tag_configure("status_401", foreground="darkorange")
        self.output_text.tag_configure("status_403", foreground="red")
        self.output_text.tag_configure("status_50x", foreground="magenta")
        self.output_text.tag_configure("error", foreground="red", font=fixed_bold)
        self.output_text.tag_configure("info", foreground="grey")
        self.output_text.tag_configure("success", foreground="green", font=fixed_bold)
        self.output_text.tag_configure("nmap_port_open", foreground="green")
        self.output_text.tag_configure("nmap_port_closed", foreground="red")
        self.output_text.tag_configure("nmap_port_filtered", foreground="orange")
        self.output_text.tag_configure("nmap_host_up", foreground="green")
        self.output_text.tag_configure("nmap_service", foreground="blue")
        self.output_text.tag_configure("sqlmap_vulnerable", foreground="red", font=fixed_bold)
        self.output_text.tag_configure("sqlmap_info", foreground="cyan")
        self.output_text.tag_configure("sqlmap_dbms", foreground="purple")
        self.output_text.tag_configure("sqlmap_data", foreground="green")
        self.output_text.tag_configure("nikto_vuln", foreground="red", font=fixed_bold)
        self.output_text.tag_configure("nikto_info", foreground="blue")
        self.output_text.tag_configure("nikto_server", foreground="purple")
        self.output_text.tag_configure("john_cracked", foreground="green", font=fixed_bold)
        self.output_text.tag_configure("john_status", foreground="grey")
        self.output_text.tag_configure("tool_not_found_msg", foreground="red", font=("TkFixedFont", 10, "italic"))

    def _apply_theme(self, theme_name: str):
        # Base palettes
        if theme_name == "Glass":
            bg = "#f5f7fb"; card = "#ffffff"; border = "#e0e6f0"; text = "#111111"; accent = "#4f46e5"
            btn_bg = "#eef1f8"; btn_fg = text
        elif theme_name == "Brutalist":
            bg = "#ffffff"; card = "#ffffff"; border = "#111111"; text = "#111111"; accent = "#ff3b30"
            btn_bg = "#ffe8e6"; btn_fg = text
        else:  # Neubrutalist default
            bg = "#f8fafc"; card = "#ffffff"; border = "#0f172a"; text = "#0f172a"; accent = "#0ea5e9"
            btn_bg = "#e6f6fd"; btn_fg = text

        try:
            self.master.configure(bg=bg)
        except Exception:
            pass
        for cls in ("TFrame", "TLabelframe", "TNotebook", "TLabel"):
            self.style.configure(cls, background=bg, foreground=text)
        self.style.configure("section.TLabelframe", background=bg)
        self.style.configure("TLabelframe", bordercolor=border)
        self.style.configure("TEntry", fieldbackground=card, background=card, foreground=text)
        self.style.configure("TCombobox", fieldbackground=card, background=card, foreground=text)
        self.style.configure("TButton", background=btn_bg, foreground=btn_fg, padding=6, borderwidth=2, focusthickness=3, focuscolor=accent)
        self.style.map("TButton", background=[("active", accent)], foreground=[("active", "#ffffff")])
        self.style.configure("TNotebook.Tab", padding=(10, 4))
        self.style.map("TNotebook.Tab", background=[("selected", card)], foreground=[("selected", text)])

        # Scrolled output text widget background/fg
        try:
            if hasattr(self, "output_text"):
                self.output_text.configure(bg=card, fg=text, insertbackground=text)
        except Exception:
            pass

    def create_widgets(self):
        # Header with logo and title
        header = ttk.Frame(self.master, padding="8 6")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8,4))
        header.columnconfigure(1, weight=1)
        try:
            if hasattr(self, "_logo_display_image"):
                logo_label = ttk.Label(header, image=self._logo_display_image)
                logo_label.grid(row=0, column=0, sticky="w")
        except Exception:
            pass
        ttk.Label(header, text="Redboar Pentesting GUI", style="AppTitle.TLabel").grid(row=0, column=1, sticky="w", padx=(8,0))

        self.main_notebook = ttk.Notebook(self.master, padding="5")
        self.main_notebook.grid(row=1, column=0, columnspan=2, sticky="new", padx=8, pady=(0,4))
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

        # Targets Tab (New)
        targets_frame = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(targets_frame, text=' Targets ')
        # Store it so we can refresh it later
        self.tool_frames["Targets"] = targets_frame
        ui_targets.create_ui(targets_frame, self)

        # Graph Tab (New)
        graph_frame = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(graph_frame, text=' Network Graph ')
        self.tool_frames["Graph"] = graph_frame
        # We need to keep a ref to the graph UI instance to call load_data if we want auto-updates
        self.graph_ui_instance = ui_graph.create_ui(graph_frame, self)

        # AI Assistant Tab
        ai_frame = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(ai_frame, text=' AI Assistant ')
        ai_ui.create_ai_tab(ai_frame, self)

        cmd_group = ttk.Labelframe(self.master, text="Command", padding="8", style="section.TLabelframe")
        cmd_group.grid(row=2, column=0, sticky="ew", padx=8, pady=(0,6))
        cmd_group.columnconfigure(1, weight=1)

        ttk.Label(cmd_group, text="Preview:", style="Heading.TLabel").grid(row=0, column=0, sticky="w", padx=(0,6), pady=(0,2))
        self.cmd_preview_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_group, textvariable=self.cmd_preview_var, state="readonly", font=("TkFixedFont", 10))
        cmd_entry.grid(row=0, column=1, sticky="ew")
        self.copy_cmd_button = ttk.Button(cmd_group, text="Copy", command=self.copy_command_to_clipboard, width=8)
        self.copy_cmd_button.grid(row=0, column=2, sticky="e", padx=(6,0))

        ttk.Label(cmd_group, text="Extra Args:").grid(row=1, column=0, sticky="w", padx=(0,6), pady=(6,0))
        extra_entry = ttk.Entry(cmd_group, textvariable=self.extra_args_var, font=("TkFixedFont", 10))
        extra_entry.grid(row=1, column=1, sticky="ew", pady=(6,0))
        ttk.Button(cmd_group, text="Clear", width=8, command=lambda: (self.extra_args_var.set(""), self.update_command_preview())).grid(row=1, column=2, sticky="e", padx=(6,0), pady=(6,0))
        self.extra_args_var.trace_add("write", lambda *args: self.update_command_preview())

        self.progress_bar = ttk.Progressbar(self.master, mode='indeterminate', length=200)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 6))
        self.progress_bar.grid_remove()

        output_group = ttk.Labelframe(self.master, text="Output", padding="8", style="section.TLabelframe")
        output_group.grid(row=4, column=0, sticky="nsew", padx=8, pady=(0,8))
        output_group.rowconfigure(1, weight=1)
        output_group.columnconfigure(0, weight=1)

        search_bar = ttk.Frame(output_group)
        search_bar.grid(row=0, column=0, sticky="ew", pady=(0,6))
        search_bar.columnconfigure(1, weight=1)
        ttk.Label(search_bar, text="Search:").grid(row=0, column=0, sticky="w")
        self.search_entry = ttk.Entry(search_bar, textvariable=self.search_var, font=("TkFixedFont", 10))
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(6,6))
        ttk.Button(search_bar, text="Find Next", command=self.find_next_in_output, width=10).grid(row=0, column=2)
        ttk.Button(search_bar, text="Clear Highlights", command=self.clear_search_highlights, width=16).grid(row=0, column=3, padx=(6,0))

        self.output_text = scrolledtext.ScrolledText(output_group, wrap=tk.WORD, height=15, font=("TkFixedFont", 10))
        self.output_text.grid(row=1, column=0, sticky="nsew")
        self.output_text.configure(state='disabled')

        control_frame = ttk.Frame(self.master, padding="8 6")
        control_frame.grid(row=5, column=0, sticky="ew", padx=8, pady=(0,8))
        # Spacer column grows, buttons align left, status right
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(8, weight=0)

        self.start_button = ttk.Button(control_frame, text="Start Scan", command=self.start_scan, width=14)
        self.start_button.grid(row=0, column=1, padx=4)
        self.stop_button = ttk.Button(control_frame, text="Stop Scan", command=self.stop_scan, state=tk.DISABLED, width=14)
        self.stop_button.grid(row=0, column=2, padx=4)
        self.clear_button = ttk.Button(control_frame, text="Clear Output", command=self.clear_output, width=14)
        self.clear_button.grid(row=0, column=3, padx=4)
        self.export_button = ttk.Button(control_frame, text="Export Text", command=self.export_results, width=14)
        self.export_button.grid(row=0, column=4, padx=4)
        self.export_html_button = ttk.Button(control_frame, text="Export HTML", command=self.export_results_html, width=14)
        self.export_html_button.grid(row=0, column=5, padx=4)
        self.status_label = ttk.Label(control_frame, text="Status: Idle", anchor="e")
        self.status_label.grid(row=0, column=8, sticky="e", padx=4)

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

    def find_next_in_output(self):
        query = self.search_var.get()
        if not query:
            return
        self.output_text.tag_configure("search_highlight", background="#ffeb3b", foreground="black")
        start_index = self._last_search_index or "1.0"
        self.output_text.focus_set()
        idx = self.output_text.search(query, start_index, stopindex=tk.END)
        if not idx:
            # Wrap to start
            idx = self.output_text.search(query, "1.0", stopindex=tk.END)
            if not idx:
                self.status_label.config(text="Status: Not found")
                return
        lastidx = f"{idx}+{len(query)}c"
        self.output_text.tag_remove("search_highlight", "1.0", tk.END)
        self.output_text.tag_add("search_highlight", idx, lastidx)
        self.output_text.see(idx)
        self._last_search_index = lastidx

    def clear_search_highlights(self):
        self.output_text.tag_remove("search_highlight", "1.0", tk.END)
        self._last_search_index = None

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

        tool_executable_key = _normalize_tool_key(tool_name_display)

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
                    
                    # --- Post-Processing Hook ---
                    # Check if we need to parse Nmap results
                    if self.proc_thread_tool_name == "Nmap" and hasattr(self, 'nmap_xml_output_path') and self.nmap_xml_output_path:
                         if os.path.exists(self.nmap_xml_output_path):
                             try:
                                 project_info = self.state_manager.get_current_project()
                                 xml_output_path = self.nmap_xml_output_path
                                 if project_info and project_info['id']:
                                     from core import parsers # Lazy import
                                     self.insert_output_line(f"\n[+] Parsing Nmap results into Project: {project_info['name']}...", ("info",))
                                     parsers.parse_nmap_xml(xml_output_path, project_info['id'])
                                     self.insert_output_line(f"[+] Parsing complete.", ("success",))
                                     # Notify specific tab observer if exists (Phase 2 UI update)
                                 else:
                                     self.insert_output_line(f"\n[!] No active project selected. Results not saved to DB.", ("error",))
                             except Exception as e:
                                 self.insert_output_line(f"\n[!] Error parsing Nmap XML: {e}", ("error",))
                             finally:
                                 # Cleanup temp file
                                 try:
                                     os.remove(self.nmap_xml_output_path)
                                     self.nmap_xml_output_path = None
                                 except OSError:
                                     pass

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
        tool_name_key = _normalize_tool_key(tool_name_display)
        
        base_executable_cmd = FOUND_EXECUTABLES.get(tool_name_key)
        if not base_executable_cmd:
            raise ValueError(f"{tool_name_display} executable not found.")
        
        cmd_list = list(base_executable_cmd)
        
        if tool_module and hasattr(tool_module, 'build_command'):
            # Some build_commands might modify app state (like nmap xml path)
            tool_specific_args = tool_module.build_command(self)
            cmd_list.extend(tool_specific_args)
        else:
            raise ValueError(f"Command builder not found for {tool_name_display}")
        # Append extra args if provided
        extra = self.extra_args_var.get().strip()
        if extra:
            try:
                extra_tokens = shlex.split(extra)
                cmd_list.extend(extra_tokens)
            except Exception as e:
                raise ValueError(f"Invalid extra args: {e}")
            
        return cmd_list

    def update_command_preview(self, event=None):
        try:
            cmd_list = self._get_command_for_current_tool()
            if hasattr(shlex, 'join'):
                preview_text = shlex.join([str(item) for item in cmd_list])
            else:
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
        current_tool_key = _normalize_tool_key(current_tool_display_name)
        
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

            # Record run start
            self._record_run_start(current_tool_display_name, args_list)

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
                if os.name == 'posix':
                    try:
                        os.killpg(os.getpgid(proc_to_stop.pid), signal.SIGTERM)
                    except Exception:
                        proc_to_stop.terminate()
                else:
                    proc_to_stop.terminate()
                try:
                    proc_to_stop.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.insert_output_line(f"\n--- {tool_name} process did not terminate quickly, sending kill signal ---", ("error",))
                    if os.name == 'posix':
                        try:
                            os.killpg(os.getpgid(proc_to_stop.pid), signal.SIGKILL)
                        except Exception:
                            proc_to_stop.kill()
                    else:
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

    def export_results_html(self):
        output_content = self.output_text.get("1.0", tk.END)
        if not output_content.strip():
            messagebox.showwarning("Export Empty", "There is no output to export.")
            return
        filepath = filedialog.asksaveasfilename(
            title="Save Output as HTML",
            defaultextension=".html",
            filetypes=(("HTML files", "*.html"), ("All files", "*.*"))
        )
        if not filepath:
            return
        try:
            tool = self.current_tool_name.get()
            cmd_preview = self.cmd_preview_var.get()
            timestamp = datetime.datetime.now().isoformat(timespec='seconds')
            html = f"""<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Redboar Output</title>
<style>body{{font-family:monospace;white-space:pre-wrap}}.meta{{font-family:sans-serif;white-space:normal;background:#f5f5f5;padding:8px;margin-bottom:8px;border:1px solid #ddd}}</style>
</head><body>
<div class=\"meta\"><strong>Tool:</strong> {tool}<br><strong>When:</strong> {timestamp}<br><strong>Command:</strong> {cmd_preview}</div>
<pre>{self._escape_html(output_content)}</pre>
</body></html>"""
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            messagebox.showinfo("Export Successful", f"HTML saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save HTML file:\n{e}")

    @staticmethod
    def _escape_html(text: str) -> str:
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))

    # Profiles and state persistence
    @property
    def _config_dir(self) -> Path:
        return Path.home() / ".config" / "redboar"

    @property
    def _profiles_path(self) -> Path:
        return self._config_dir / "profiles.json"
    
    def new_project_dialog(self):
        name = simpledialog.askstring("New Project", "Enter Project Name:")
        if name:
            try:
                self.state_manager.create_project(name)
                self.title_update()
                messagebox.showinfo("Project", f"Created and switched to project: {name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create project: {e}")

    def open_project_dialog(self):
        projects = self.state_manager.get_all_projects()
        if not projects:
            messagebox.showinfo("Project", "No projects found.")
            return

        # Simple list dialog
        top = tk.Toplevel(self.master)
        top.title("Open Project")
        listbox = tk.Listbox(top, width=50)
        listbox.pack(padx=10, pady=10)
        
        for p in projects:
            listbox.insert(tk.END, f"{p['name']} (ID: {p['id']})")
            
        def select_proj():
            sel = listbox.curselection()
            if sel:
                idx = sel[0]
                proj = projects[idx]
                self.state_manager.load_project(proj['id'])
                self.title_update()
                top.destroy()
                messagebox.showinfo("Project", f"Switched to project: {proj['name']}")
                
        ttk.Button(top, text="Open", command=select_proj).pack(pady=5)

    def show_project_info(self):
        proj = self.state_manager.get_current_project()
        if proj['id']:
            messagebox.showinfo("Project Info", f"Active Project: {proj['name']}\nID: {proj['id']}")
        else:
            messagebox.showinfo("Project Info", "No active project.")

    def title_update(self):
         proj = self.state_manager.get_current_project()
         title = "Redboar Pentesting GUI"
         if proj['name']:
             title += f" - [{proj['name']}]"
         self.master.title(title)

    @property
    def _state_path(self) -> Path:
        return self._config_dir / "state.json"

    @property
    def _runs_path(self) -> Path:
        return self._config_dir / "runs.jsonl"

    def _ensure_config_dir(self):
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Failed to create config dir: %s", e)

    def save_profile(self):
        name = simpledialog.askstring("Save Profile", "Enter profile name:")
        if not name:
            return
        self._ensure_config_dir()
        profile = self._collect_state(include_current_tool=True)
        try:
            data = {}
            if self._profiles_path.exists():
                with open(self._profiles_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data[name] = profile
            with open(self._profiles_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Profile Saved", f"Profile '{name}' saved.")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save profile:\n{e}")

    def load_profile(self):
        name = simpledialog.askstring("Load Profile", "Enter profile name:")
        if not name:
            return
        try:
            if not self._profiles_path.exists():
                messagebox.showwarning("Load Profile", "No profiles found.")
                return
            with open(self._profiles_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            profile = data.get(name)
            if not profile:
                messagebox.showwarning("Load Profile", f"Profile '{name}' not found.")
                return
            self._apply_state(profile)
            self.update_command_preview()
            messagebox.showinfo("Profile Loaded", f"Profile '{name}' loaded.")
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load profile:\n{e}")

    def _collect_state(self, include_current_tool: bool = False) -> dict:
        state = {
            "extra_args": self.extra_args_var.get(),
            "tools": {
                "Gobuster": {
                    "mode": getattr(self, 'gobuster_current_mode_var', tk.StringVar(value='Directory/File')).get(),
                    "target": getattr(self, 'gobuster_target_var', tk.StringVar()).get(),
                    "wordlist": getattr(self, 'gobuster_wordlist_var', tk.StringVar()).get(),
                    "threads": getattr(self, 'gobuster_threads_var', tk.StringVar(value='10')).get(),
                    "extensions": getattr(self, 'gobuster_extensions_var', tk.StringVar()).get(),
                    "status_codes": getattr(self, 'gobuster_status_codes_var', tk.StringVar()).get(),
                },
                "Nmap": {
                    "target": getattr(self, 'nmap_target_var', tk.StringVar()).get(),
                    "ports": getattr(self, 'nmap_ports_var', tk.StringVar()).get(),
                    "scan_types": {k: v.get() for k, v in getattr(self, 'nmap_scan_type_vars', {}).items()},
                    "ping_scan": getattr(self, 'nmap_ping_scan_var', tk.BooleanVar()).get(),
                    "no_ping": getattr(self, 'nmap_no_ping_var', tk.BooleanVar(value=True)).get(),
                    "os_detect": getattr(self, 'nmap_os_detect_var', tk.BooleanVar(value=True)).get(),
                    "version_detect": getattr(self, 'nmap_version_detect_var', tk.BooleanVar(value=True)).get(),
                    "fast_scan": getattr(self, 'nmap_fast_scan_var', tk.BooleanVar()).get(),
                    "verbose": getattr(self, 'nmap_verbose_var', tk.BooleanVar(value=True)).get(),
                },
                "SQLMap": {
                    "target": getattr(self, 'sqlmap_target_var', tk.StringVar()).get(),
                    "batch": getattr(self, 'sqlmap_batch_var', tk.BooleanVar(value=True)).get(),
                    "dbs": getattr(self, 'sqlmap_dbs_var', tk.BooleanVar()).get(),
                    "current_db": getattr(self, 'sqlmap_current_db_var', tk.BooleanVar()).get(),
                    "tables": getattr(self, 'sqlmap_tables_var', tk.BooleanVar()).get(),
                    "dump": getattr(self, 'sqlmap_dump_var', tk.BooleanVar()).get(),
                    "db_name": getattr(self, 'sqlmap_db_name_var', tk.StringVar()).get(),
                    "table_name": getattr(self, 'sqlmap_table_name_var', tk.StringVar()).get(),
                    "level": getattr(self, 'sqlmap_level_var', tk.StringVar(value='1')).get(),
                    "risk": getattr(self, 'sqlmap_risk_var', tk.StringVar(value='1')).get(),
                },
                "Nikto": {
                    "target": getattr(self, 'nikto_target_var', tk.StringVar()).get(),
                    "format": getattr(self, 'nikto_format_var', tk.StringVar(value='txt')).get(),
                    "tuning": getattr(self, 'nikto_tuning_var', tk.StringVar(value='x 123b')).get(),
                    "ssl": getattr(self, 'nikto_ssl_var', tk.BooleanVar()).get(),
                    "ask_no": getattr(self, 'nikto_ask_no_var', tk.BooleanVar(value=True)).get(),
                },
                "John the Ripper": {
                    "hash_file": getattr(self, 'john_hash_file_var', tk.StringVar()).get(),
                    "wordlist": getattr(self, 'john_wordlist_var', tk.StringVar()).get(),
                    "format": getattr(self, 'john_format_var', tk.StringVar()).get(),
                    "session": getattr(self, 'john_session_var', tk.StringVar()).get(),
                    "show": getattr(self, 'john_show_cracked_var', tk.BooleanVar()).get(),
                },
            }
        }
        if include_current_tool:
            state["current_tool"] = self.current_tool_name.get()
        return state

    def _apply_state(self, state: dict):
        try:
            self.extra_args_var.set(state.get("extra_args", ""))
            tools = state.get("tools", {})
            g = tools.get("Gobuster", {})
            if g:
                self.gobuster_current_mode_var.set(g.get("mode", self.gobuster_current_mode_var.get()))
                self.gobuster_target_var.set(g.get("target", ""))
                self.gobuster_wordlist_var.set(g.get("wordlist", ""))
                self.gobuster_threads_var.set(g.get("threads", self.gobuster_threads_var.get()))
                self.gobuster_extensions_var.set(g.get("extensions", ""))
                self.gobuster_status_codes_var.set(g.get("status_codes", self.gobuster_status_codes_var.get()))
            n = tools.get("Nmap", {})
            if n:
                self.nmap_target_var.set(n.get("target", ""))
                self.nmap_ports_var.set(n.get("ports", ""))
                scan_types = n.get("scan_types", {})
                for k, var in getattr(self, 'nmap_scan_type_vars', {}).items():
                    var.set(bool(scan_types.get(k, var.get())))
                self.nmap_ping_scan_var.set(n.get("ping_scan", self.nmap_ping_scan_var.get()))
                self.nmap_no_ping_var.set(n.get("no_ping", self.nmap_no_ping_var.get()))
                self.nmap_os_detect_var.set(n.get("os_detect", self.nmap_os_detect_var.get()))
                self.nmap_version_detect_var.set(n.get("version_detect", self.nmap_version_detect_var.get()))
                self.nmap_fast_scan_var.set(n.get("fast_scan", self.nmap_fast_scan_var.get()))
                self.nmap_verbose_var.set(n.get("verbose", self.nmap_verbose_var.get()))
            s = tools.get("SQLMap", {})
            if s:
                self.sqlmap_target_var.set(s.get("target", ""))
                self.sqlmap_batch_var.set(s.get("batch", self.sqlmap_batch_var.get()))
                self.sqlmap_dbs_var.set(s.get("dbs", self.sqlmap_dbs_var.get()))
                self.sqlmap_current_db_var.set(s.get("current_db", self.sqlmap_current_db_var.get()))
                self.sqlmap_tables_var.set(s.get("tables", self.sqlmap_tables_var.get()))
                self.sqlmap_dump_var.set(s.get("dump", self.sqlmap_dump_var.get()))
                self.sqlmap_db_name_var.set(s.get("db_name", self.sqlmap_db_name_var.get()))
                self.sqlmap_table_name_var.set(s.get("table_name", self.sqlmap_table_name_var.get()))
                self.sqlmap_level_var.set(s.get("level", self.sqlmap_level_var.get()))
                self.sqlmap_risk_var.set(s.get("risk", self.sqlmap_risk_var.get()))
            k = tools.get("Nikto", {})
            if k:
                self.nikto_target_var.set(k.get("target", ""))
                self.nikto_format_var.set(k.get("format", self.nikto_format_var.get()))
                self.nikto_tuning_var.set(k.get("tuning", self.nikto_tuning_var.get()))
                self.nikto_ssl_var.set(k.get("ssl", self.nikto_ssl_var.get()))
                self.nikto_ask_no_var.set(k.get("ask_no", self.nikto_ask_no_var.get()))
            j = tools.get("John the Ripper", {})
            if j:
                self.john_hash_file_var.set(j.get("hash_file", ""))
                self.john_wordlist_var.set(j.get("wordlist", ""))
                self.john_format_var.set(j.get("format", ""))
                self.john_session_var.set(j.get("session", ""))
                self.john_show_cracked_var.set(j.get("show", self.john_show_cracked_var.get()))
            if state.get("current_tool") in self.tool_frames:
                desired = state.get("current_tool")
                idx = list(self.tool_frames.keys()).index(desired)
                self.main_notebook.select(idx)
        except Exception as e:
            logger.warning("Failed to apply state: %s", e)

    def _load_state(self):
        try:
            if self._state_path.exists():
                with open(self._state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self._apply_state(state)
        except Exception as e:
            logger.warning("Failed to load state: %s", e)

    def _save_state(self):
        try:
            self._ensure_config_dir()
            state = self._collect_state(include_current_tool=True)
            with open(self._state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save state: %s", e)

    def _record_run_start(self, tool_name: str, cmd: list):
        try:
            self._ensure_config_dir()
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "tool": tool_name,
                "command": cmd,
            }
            with open(self._runs_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.debug("Failed to record run: %s", e)

    def on_close(self):
        try:
            self._save_state()
        finally:
            self.master.destroy()

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

def attempt_auto_install_missing_tools(missing_tool_info):
    try:
        # Only attempt on apt-based distros (e.g., Kali)
        if not (sys.platform.startswith('linux') and which('apt')):
            return False
        tools_to_install = []
        for tool_key, _display_name in missing_tool_info:
            pkg = config.COMMON_PACKAGE_NAMES.get(tool_key)
            if pkg:
                tools_to_install.append(pkg)
        if not tools_to_install:
            return False
        confirm = messagebox.askyesno(
            "Install Missing Tools",
            "Some tools are missing. On Kali/apt systems I can install them automatically with sudo.\n\n"
            f"Packages to install: {', '.join(tools_to_install)}\n\nProceed?")
        if not confirm:
            return False
        # Run apt install
        import subprocess as _sp
        cmd = ["sudo", "apt", "update"]
        _sp.run(cmd, check=False)
        cmd = ["sudo", "apt", "install", "-y", *tools_to_install]
        _sp.run(cmd, check=False)
        # Re-detect executables
        for tool_key in config.EXECUTABLE_PATHS.keys():
            FOUND_EXECUTABLES[tool_key] = None
            find_executable(tool_key)
        return True
    except Exception as e:
        logger.warning("Auto-install failed: %s", e)
        return False

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
        installed = attempt_auto_install_missing_tools(missing_tool_details)
        if not installed:
            display_tool_installation_guidance(missing_tool_details)

    root.deiconify()
    app = PentestApp(root)
    # Load last state if available
    app._load_state()
    # Ensure state is saved on exit
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
