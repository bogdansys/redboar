import tkinter as tk
from tkinter import ttk
import logging
import db
import automation_engine
from tkinter import simpledialog, messagebox

logger = logging.getLogger("redboar")

def create_ui(parent_frame, app_instance):
    """
    Creates the Targets UI tab.
    """
    parent_frame.columnconfigure(0, weight=1)
    parent_frame.rowconfigure(1, weight=1)

    # Top control bar
    top_bar = ttk.Frame(parent_frame, padding="5")
    top_bar.grid(row=0, column=0, sticky="ew")
    
    ttk.Button(top_bar, text="Refresh Data", command=lambda: refresh_data(app_instance)).pack(side="left", padx=5)
    
    # Checkbutton to show only alive hosts? (Maybe later)
    
    # Split pane: Hosts on left, Services on right
    paned = ttk.PanedWindow(parent_frame, orient=tk.HORIZONTAL)
    paned.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    # --- Left Pane: Hosts ---
    hosts_frame = ttk.Labelframe(paned, text="Hosts", padding="5")
    paned.add(hosts_frame, weight=1)
    
    # Treeview for hosts
    columns = ("ip", "hostname", "os", "status")
    app_instance.targets_host_tree = ttk.Treeview(hosts_frame, columns=columns, show="headings")
    app_instance.targets_host_tree.heading("ip", text="IP Address")
    app_instance.targets_host_tree.heading("hostname", text="Hostname")
    app_instance.targets_host_tree.heading("os", text="OS")
    app_instance.targets_host_tree.heading("status", text="Status")
    
    app_instance.targets_host_tree.column("ip", width=120)
    app_instance.targets_host_tree.column("hostname", width=150)
    app_instance.targets_host_tree.column("os", width=150)
    app_instance.targets_host_tree.column("status", width=80)
    
    hosts_scroll = ttk.Scrollbar(hosts_frame, orient="vertical", command=app_instance.targets_host_tree.yview)
    app_instance.targets_host_tree.configure(yscrollcommand=hosts_scroll.set)
    
    # Configure tags
    app_instance.targets_host_tree.tag_configure("up", foreground="green")
    app_instance.targets_host_tree.tag_configure("down", foreground="red")
    
    app_instance.targets_host_tree.pack(side="left", fill="both", expand=True)
    hosts_scroll.pack(side="right", fill="y")
    
    # Bind click event
    app_instance.targets_host_tree.bind("<<TreeviewSelect>>", lambda e: on_host_select(app_instance))
    
    # Context Menu
    app_instance.targets_host_menu = tk.Menu(parent_frame, tearoff=0)
    app_instance.targets_host_menu.add_command(label="Auto-Scan (Reactive)", command=lambda: run_auto_scan(app_instance))
    
    app_instance.targets_host_tree.bind("<Button-3>", lambda e: show_context_menu(e, app_instance.targets_host_menu))

    # --- Right Pane: Services ---
    services_frame = ttk.Labelframe(paned, text="Services / Ports", padding="5")
    paned.add(services_frame, weight=2)
    
    svc_columns = ("port", "proto", "service", "product", "version", "state")
    app_instance.targets_svc_tree = ttk.Treeview(services_frame, columns=svc_columns, show="headings")
    app_instance.targets_svc_tree.heading("port", text="Port")
    app_instance.targets_svc_tree.heading("proto", text="Proto")
    app_instance.targets_svc_tree.heading("service", text="Service")
    app_instance.targets_svc_tree.heading("product", text="Product")
    app_instance.targets_svc_tree.heading("version", text="Version")
    app_instance.targets_svc_tree.heading("state", text="State")
    
    app_instance.targets_svc_tree.column("port", width=60)
    app_instance.targets_svc_tree.column("proto", width=60)
    app_instance.targets_svc_tree.column("service", width=100)
    app_instance.targets_svc_tree.column("product", width=120)
    app_instance.targets_svc_tree.column("version", width=100)
    app_instance.targets_svc_tree.column("state", width=80)
    
    # Configure tags
    app_instance.targets_svc_tree.tag_configure("open", foreground="green")
    app_instance.targets_svc_tree.tag_configure("closed", foreground="red")
    app_instance.targets_svc_tree.tag_configure("filtered", foreground="orange")
    
    svc_scroll = ttk.Scrollbar(services_frame, orient="vertical", command=app_instance.targets_svc_tree.yview)
    app_instance.targets_svc_tree.configure(yscrollcommand=svc_scroll.set)
    
    app_instance.targets_svc_tree.pack(side="left", fill="both", expand=True)
    svc_scroll.pack(side="right", fill="y")

    # Initial load attempt
    refresh_data(app_instance)

def refresh_data(app):
    """Refreshes the host list from the database for the current project."""
    # Clear current
    for item in app.targets_host_tree.get_children():
        app.targets_host_tree.delete(item)
    for item in app.targets_svc_tree.get_children():
        app.targets_svc_tree.delete(item)
            
    proj = app.state_manager.get_current_project()
    if not proj['id']:
        return

    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, ip_address, hostname, os_name, status FROM hosts WHERE project_id=? ORDER BY ip_address", 
            (proj['id'],)
        )
        hosts = cursor.fetchall()
        for h in hosts:
            status = h['status'] or ""
            tags = (status,) if status in ("up", "down") else ()
            app.targets_host_tree.insert(
                "", "end", iid=str(h['id']),
                values=(h['ip_address'], h['hostname'], h['os_name'], status),
                tags=tags
            )
    except Exception as e:
        logger.error(f"Error loading targets: {e}")
    finally:
        conn.close()

def on_host_select(app):
    """Loads services for the selected host."""
    selected = app.targets_host_tree.selection()
    if not selected:
        return
    
    host_id = selected[0]
    
    # Clear services
    for item in app.targets_svc_tree.get_children():
        app.targets_svc_tree.delete(item)
        
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT port, protocol, service_name, product, version, state FROM services WHERE host_id=? ORDER BY port", 
            (host_id,)
        )
        services = cursor.fetchall()
        for s in services:
            state = s['state'] or ""
            tags = (state,) if state in ("open", "closed", "filtered") else ()
            app.targets_svc_tree.insert(
                "", "end", 
                values=(s['port'], s['protocol'], s['service_name'], s['product'], s['version'], state),
                tags=tags
            )
    except Exception as e:
        logger.error(f"Error loading services: {e}")
    finally:
        conn.close()

def show_context_menu(event, menu):
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

def run_auto_scan(app):
    selected = app.targets_host_tree.selection()
    if not selected:
        return
    
    host_id = selected[0]
    proj = app.state_manager.get_current_project()
    if not proj['id']:
        return

    # Check for proposals
    proposals = automation_engine.propose_scans(proj['id'], host_id)
    
    if not proposals:
        messagebox.showinfo("Auto-Scan", "No automated workflows triggered for this host based on current rules.")
        return
        
    show_job_proposals(app, proposals)

def show_job_proposals(app, proposals):
    """
    Dialog to let user select which proposed jobs to run.
    """
    top = tk.Toplevel(app.master)
    top.title("Auto-Scan Recommendations")
    top.geometry("600x400")
    
    ttk.Label(top, text="The following tools are recommended based on open ports:", font=("Segoe UI", 10, "bold")).pack(pady=10)
    
    # Checkbox list
    vars_map = {} # proposal -> BooleanVar
    
    frame = ttk.Frame(top)
    frame.pack(fill="both", expand=True, padx=10)
    
    # Canvas for scrolling if many
    canvas = tk.Canvas(frame)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    for prop in proposals:
        var = tk.BooleanVar(value=True) # Default checked
        vars_map[prop] = var
        c = ttk.Checkbutton(scrollable_frame, text=f"{prop.label}\n   Reason: {prop.reason}", variable=var)
        c.pack(anchor="w", pady=5)
        
    def execute():
        to_run = [p for p, v in vars_map.items() if v.get()]
        top.destroy()
        execute_approved_jobs(app, to_run)
        
    ttk.Button(top, text="Run Selected", command=execute).pack(pady=10)

def execute_approved_jobs(app, jobs):
    """
    Executes the list of jobs by opening their respective tabs and pre-filling params.
    """
    if not jobs:
        return
        
    # We only auto-fill the first job for now to prevent tab switching chaos,
    # or we could try to fill all. Let's fill all but switch to the last one.
    
    for job in jobs:
        tool_name = job.tool_name
        
        # 1. Switch to Tab
        target_frame = app.tool_frames.get(tool_name)
        if target_frame:
            app.main_notebook.select(target_frame)
        else:
            logger.warning(f"Could not find tab for tool: {tool_name}")
            continue
            
        # 2. Map Params to UI Variables
        # This requires knowledge of how each tool UI names its variables.
        # Future Refactor: Make tools register their param inputs in a standard way.
        
        try:
            if tool_name == "Nikto":
                if "target" in job.params:
                    # ui_nikto uses nikto_target_var
                    if hasattr(app, "nikto_target_var"):
                        app.nikto_target_var.set(job.params["target"])
                # We could map other params like SSL but for now Target is key.
                
            elif tool_name == "Gobuster":
                # Assuming ui_gobuster uses gobuster_url_var (need to verify or try generic)
                # If checking checks fails, we just log.
                if "target" in job.params and hasattr(app, "gobuster_target_var"):
                     app.gobuster_target_var.set(job.params["target"])
                # Alternative naming?
                elif "target" in job.params and hasattr(app, "gobuster_url_var"):
                     app.gobuster_url_var.set(job.params["target"])

            elif tool_name == "Nmap":
                 # ui_nmap uses nmap_target_var and nmap_type_var
                 if "target" in job.params and hasattr(app, "nmap_target_var"):
                     app.nmap_target_var.set(job.params["target"])
                 if "scan_type" in job.params and hasattr(app, "nmap_custom_flags_var"):
                      # Nmap UI is complex (Combobox + Custom). 
                      # Let's set custom args var if passing specific flags.
                      app.nmap_custom_flags_var.set(job.params["scan_type"])
                      
            # 3. Update Preview
            if hasattr(app, "update_command_preview"):
                app.update_command_preview()
                
        except Exception as e:
            logger.error(f"Error auto-filling job {tool_name}: {e}")
            
    messagebox.showinfo("Automation", f"Pre-filled {len(jobs)} jobs.\nPlease review the tabs and click 'Start' to begin execution.")

