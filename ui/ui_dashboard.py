import tkinter as tk
from tkinter import ttk
import logging
from core import db

logger = logging.getLogger("redboar")

class DashboardUI:
    def __init__(self, parent_frame, app_instance):
        self.app = app_instance
        self.parent = parent_frame
        self.setup_ui()

    def setup_ui(self):
        # Header
        self.header_frame = ttk.Frame(self.parent, padding=10)
        self.header_frame.pack(fill="x", side="top")
        
        ttk.Label(self.header_frame, text="Mission Control", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(self.header_frame, text="Refresh Stats", command=self.refresh_stats).pack(side="right")

        # KPI Cards Frame
        self.kpi_frame = ttk.Frame(self.parent, padding=10)
        self.kpi_frame.pack(fill="x", side="top")
        
        # We will create card-like labels here
        self.card_hosts_up = self._create_card(self.kpi_frame, "Hosts Up", "0", "green")
        self.card_hosts_down = self._create_card(self.kpi_frame, "Hosts Down", "0", "red")
        self.card_services = self._create_card(self.kpi_frame, "Open Services", "0", "blue")
        self.card_vulns = self._create_card(self.kpi_frame, "Potential Vulns", "0", "orange") # Placeholder for now

        # Charts Area (Txt/Canvas based)
        self.chart_frame = ttk.LabelFrame(self.parent, text="Top Services", padding=10)
        self.chart_frame.pack(fill="both", expand=True, side="top", padx=10, pady=10)
        
        self.chart_canvas = tk.Canvas(self.chart_frame, bg="#e0e0e0", height=200)
        self.chart_canvas.pack(fill="both", expand=True)
        
        # Initial Load
        self.refresh_stats()

    def _create_card(self, parent, title, value, color):
        frame = tk.Frame(parent, bg="white", padx=10, pady=10, relief="raised", borderwidth=1)
        frame.pack(side="left", fill="both", expand=True, padx=5)
        
        lbl_val = tk.Label(frame, text=value, font=("Segoe UI", 24, "bold"), fg=color, bg="white")
        lbl_val.pack(anchor="center")
        
        lbl_title = tk.Label(frame, text=title, font=("Segoe UI", 10), fg="#555", bg="white")
        lbl_title.pack(anchor="center")
        return lbl_val

    def refresh_stats(self):
        proj_id = self.app.state_manager.current_project_id
        if not proj_id:
            return

        try:
            conn = db.get_connection()
            cur = conn.cursor()
            
            # KPI 1: Hosts Up
            cur.execute("SELECT COUNT(*) FROM hosts WHERE project_id=? AND status='up'", (proj_id,))
            count_up = cur.fetchone()[0]
            self.card_hosts_up.config(text=str(count_up))

            # KPI 2: Hosts Down
            cur.execute("SELECT COUNT(*) FROM hosts WHERE project_id=? AND status='down'", (proj_id,))
            count_down = cur.fetchone()[0]
            self.card_hosts_down.config(text=str(count_down))
            
            # KPI 3: Open Services
            cur.execute("SELECT COUNT(*) FROM services JOIN hosts ON services.host_id=hosts.id WHERE hosts.project_id=? AND services.state='open'", (proj_id,))
            count_srv = cur.fetchone()[0]
            self.card_services.config(text=str(count_srv))
            
            # KPI 4: Vulns (Mock for now, or check notes)
            self.card_vulns.config(text="--")

            # Chart: Top 5 Ports
            cur.execute("""
                SELECT port, COUNT(*) as c 
                FROM services 
                JOIN hosts ON services.host_id=hosts.id 
                WHERE hosts.project_id=? AND services.state='open'
                GROUP BY port 
                ORDER BY c DESC 
                LIMIT 5
            """, (proj_id,))
            top_ports = cur.fetchall()
            
            self._draw_chart(top_ports)
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Dashboard refresh error: {e}")

    def _draw_chart(self, data):
        self.chart_canvas.delete("all")
        if not data:
            self.chart_canvas.create_text(20, 20, text="No data available", anchor="nw")
            return
            
        w = self.chart_canvas.winfo_width()
        h = self.chart_canvas.winfo_height()
        if w < 50: w = 400 # Fallback before render
        
        max_val = data[0][1]
        if max_val == 0: max_val = 1
        
        bar_width = min(50, (w - 100) / len(data))
        spacing = 20
        x = 50
        base_y = h - 30
        
        for port, count in data:
            bar_h = (count / max_val) * (h - 60)
            
            # Bar
            self.chart_canvas.create_rectangle(x, base_y - bar_h, x + bar_width, base_y, fill="#4a90e2", outline="")
            
            # Text
            self.chart_canvas.create_text(x + bar_width/2, base_y + 15, text=str(port))
            self.chart_canvas.create_text(x + bar_width/2, base_y - bar_h - 10, text=str(count))
            
            x += bar_width + spacing

def create_ui(parent_frame, app_instance):
    return DashboardUI(parent_frame, app_instance)
