
import tkinter as tk
from tkinter import ttk
import logging
from core import db, audit

logger = logging.getLogger("redboar")

class TimelineUI:
    def __init__(self, parent_frame, main_app):
        self.parent = parent_frame
        self.app = main_app
        self.project_id = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Header
        header = ttk.Frame(self.parent, padding="5")
        header.pack(fill="x")
        
        ttk.Label(header, text="Project Timeline", font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side="right")
        
        # Filter Frame
        filter_frame = ttk.Frame(self.parent, padding="5")
        filter_frame.pack(fill="x")
        
        ttk.Label(filter_frame, text="Filter Category:").pack(side="left", padx=5)
        self.category_var = tk.StringVar(value="ALL")
        cat_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, 
                                 values=["ALL", "SYSTEM", "SCAN", "NOTE", "REPORT", "PAYLOAD"], 
                                 state="readonly", width=15)
        cat_combo.pack(side="left", padx=5)
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # Treeview
        self.tree_frame = ttk.Frame(self.parent)
        self.tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        columns = ("timestamp", "category", "message")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("timestamp", text="Time")
        self.tree.heading("category", text="Category")
        self.tree.heading("message", text="Event")
        
        self.tree.column("timestamp", width=150, stretch=False)
        self.tree.column("category", width=100, stretch=False)
        self.tree.column("message", stretch=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def load_data(self):
        """Loads timeline events for the current project."""
        proj = self.app.state_manager.get_current_project()
        if not proj or not proj['id']:
            self.project_id = None
            self._clear_tree()
            return
            
        self.project_id = proj['id']
        self.refresh()
        
    def refresh(self):
        self._clear_tree()
        if not self.project_id:
            return

        cat_filter = self.category_var.get()
        
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            
            query = "SELECT timestamp, category, message, details FROM timeline WHERE project_id = ? "
            params = [self.project_id]
            
            if cat_filter != "ALL":
                query += "AND category = ? "
                params.append(cat_filter)
                
            query += "ORDER BY timestamp DESC"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            conn.close()
            
            for row in rows:
                # Basic formatting for timestamp (remove microseconds for cleaner look)
                ts = row['timestamp'].split('.')[0].replace('T', ' ')
                self.tree.insert("", "end", values=(ts, row['category'], row['message']))
                
        except Exception as e:
            logger.error(f"Failed to load timeline: {e}")

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

def create_ui(parent_frame, app_instance):
    return TimelineUI(parent_frame, app_instance)
