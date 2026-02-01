import tkinter as tk
from tkinter import ttk
import logging
import random
import math
import db
import graph_engine

logger = logging.getLogger("redboar")

class GraphUI:
    def __init__(self, parent_frame, app_instance):
        self.app = app_instance
        self.parent = parent_frame
        
        # Engine
        self.sim = graph_engine.GraphSimulation()
        self.running = False
        
        # UI Setup
        self.setup_ui()
        
        # Interaction state
        self.drag_data = {"node_uid": None, "x": 0, "y": 0}
        self.zoom_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
    def setup_ui(self):
        # Controls
        ctrl_frame = ttk.Frame(self.parent, padding="5")
        ctrl_frame.pack(fill="x", side="top")
        
        ttk.Button(ctrl_frame, text="Refresh Graph", command=self.load_data).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="Center View", command=self.reset_view).pack(side="left", padx=5)
        
        # Legend
        ttk.Label(ctrl_frame, text="  Legend: ", font=("Segoe UI", 9, "bold")).pack(side="left")
        
        # Canvas Legend Helper
        cw = tk.Canvas(ctrl_frame, width=100, height=20, bg=self.get_bg_color(), highlightthickness=0)
        cw.pack(side="left")
        cw.create_oval(5, 5, 15, 15, fill="green", outline="white")
        cw.create_text(20, 10, text="Host Up", anchor="w", fill="white" if "dark" in self.get_bg_color() else "black")
        cw.create_oval(60, 5, 70, 15, fill="red", outline="white")
        cw.create_text(75, 10, text="Down", anchor="w", fill="white" if "dark" in self.get_bg_color() else "black")

        # Main Canvas
        self.canvas = tk.Canvas(self.parent, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_zoom)

    def get_bg_color(self):
        # Fallback logic to guess theme, or just hardcode dark for "hacker" feel
        return "#1e1e1e" # Dark slate

    def reset_view(self):
        self.zoom_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

    def load_data(self):
        proj_id = self.app.state_manager.current_project_id
        if not proj_id:
            return

        self.sim.clear()
        
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            
            # Fetch Hosts
            cur.execute("SELECT id, ip_address, hostname, status FROM hosts WHERE project_id=?", (proj_id,))
            hosts = cur.fetchall()
            
            host_map = {}
            for h in hosts:
                uid = f"h_{h['id']}"
                host_map[h['id']] = uid
                group = "host_up" if h['status'] == 'up' else "host_down"
                
                # Random initial pos near center
                x = self.sim.width/2 + random.randint(-50, 50)
                y = self.sim.height/2 + random.randint(-50, 50)
                
                node = graph_engine.Node(uid, h['ip_address'], group=group, x=x, y=y, radius=25)
                self.sim.add_node(node)
                
            # Fetch Services (Link to Hosts)
            cur.execute("SELECT id, host_id, port, service_name, state FROM services JOIN hosts ON services.host_id = hosts.id WHERE hosts.project_id=?", (proj_id,))
            services = cur.fetchall()
            
            for s in services:
                uid = f"s_{s['id']}"
                parent_uid = host_map.get(s['host_id'])
                if not parent_uid: continue
                
                # Service Node
                # Spawn near parent
                parent_node = self.sim.nodes[parent_uid]
                x = parent_node.x + random.randint(-20, 20)
                y = parent_node.y + random.randint(-20, 20)
                
                group = "service_open" if s['state'] == 'open' else "service_closed"
                
                node = graph_engine.Node(uid, f"{s['port']}\n{s['service_name']}", group=group, x=x, y=y, radius=12)
                self.sim.add_node(node)
                
                # Edge
                edge = graph_engine.Edge(parent_uid, uid, length=60)
                self.sim.add_edge(edge)
                
        except Exception as e:
            logger.error(f"Graph load error: {e}")
        finally:
            conn.close()

        if not self.running:
            self.running = True
            self.animate()

    def animate(self):
        if not self.running: return
        
        # Physics Step
        self.sim.step()
        
        # Render
        self.draw()
        
        # Loop
        self.parent.after(20, self.animate)

    def draw(self):
        self.canvas.delete("all")
        
        cx, cy = self.canvas.winfo_width()/2, self.canvas.winfo_height()/2
        
        # Draw Edges first
        for edge in self.sim.edges:
            n1 = self.sim.nodes.get(edge.source_uid)
            n2 = self.sim.nodes.get(edge.target_uid)
            if n1 and n2:
                x1, y1 = self.transform(n1.x, n1.y, cx, cy)
                x2, y2 = self.transform(n2.x, n2.y, cx, cy)
                self.canvas.create_line(x1, y1, x2, y2, fill="#555555", width=1)
                
        # Draw Nodes
        for node in self.sim.nodes.values():
            x, y = self.transform(node.x, node.y, cx, cy)
            r = node.radius * self.zoom_scale
            
            color = "#888888"
            if node.group == "host_up": color = "#00FF00" # Green
            elif node.group == "host_down": color = "#FF0000" # Red
            elif node.group == "service_open": color = "#00AA00" # Dark Green
            
            # Circle
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="white", tags=("node", node.uid))
            
            # Text
            font_size = int(10 * self.zoom_scale)
            if font_size > 6:
                self.canvas.create_text(x, y, text=node.label, fill="white", font=("Arial", font_size), tags=("text", node.uid))

    def transform(self, x, y, cx, cy):
        # Apply zoom + pan offset relative to center
        # Assuming sim world 0,0 is top left, but we want centered.
        # Actually our sim center logic tries to keep nodes at width/2.
        
        # Scale first
        sx = (x - self.sim.width/2) * self.zoom_scale
        sy = (y - self.sim.height/2) * self.zoom_scale
        
        # Apply Pan
        return cx + sx + self.offset_x, cy + sy + self.offset_y

    def inverse_transform(self, sx, sy, cx, cy):
        # Convert Screen coords back to SIM coords
        # (sx - (cx + off)) / scale + w/2 = x
        x = (sx - (cx + self.offset_x)) / self.zoom_scale + self.sim.width/2
        y = (sy - (cy + self.offset_y)) / self.zoom_scale + self.sim.height/2
        return x, y

    def on_press(self, event):
        # Check if clicked node
        cx, cy = self.canvas.winfo_width()/2, self.canvas.winfo_height()/2
        mx, my = self.inverse_transform(event.x, event.y, cx, cy)
        
        # Find closest node
        clicked_node = None
        min_dist = 1000
        
        for node in self.sim.nodes.values():
            dist = math.hypot(node.x - mx, node.y - my)
            if dist < node.radius + 5: # Tolerance
                if dist < min_dist:
                    min_dist = dist
                    clicked_node = node
                    
        if clicked_node:
            self.drag_data["node_uid"] = clicked_node.uid
            clicked_node.fixed = True
        else:
            # Pan start
            self.drag_data["node_uid"] = None
            self.drag_data["last_x"] = event.x
            self.drag_data["last_y"] = event.y

    def on_drag(self, event):
        if self.drag_data["node_uid"]:
            # Move node
            cx, cy = self.canvas.winfo_width()/2, self.canvas.winfo_height()/2
            ts_x, ts_y = self.inverse_transform(event.x, event.y, cx, cy)
            
            node = self.sim.nodes[self.drag_data["node_uid"]]
            node.x = ts_x
            node.y = ts_y
            node.vx = 0 # Stop momentum
            node.vy = 0
        elif "last_x" in self.drag_data:
            # Pan
            dx = event.x - self.drag_data["last_x"]
            dy = event.y - self.drag_data["last_y"]
            self.offset_x += dx
            self.offset_y += dy
            self.drag_data["last_x"] = event.x
            self.drag_data["last_y"] = event.y

    def on_release(self, event):
        if self.drag_data["node_uid"]:
             node = self.sim.nodes[self.drag_data["node_uid"]]
             node.fixed = False
             self.drag_data["node_uid"] = None
        if "last_x" in self.drag_data:
             del self.drag_data["last_x"]

    def on_zoom(self, event):
        if event.delta > 0:
            self.zoom_scale *= 1.1
        else:
            self.zoom_scale *= 0.9
        # Clamp
        if self.zoom_scale < 0.1: self.zoom_scale = 0.1
        if self.zoom_scale > 5.0: self.zoom_scale = 5.0


def create_ui(parent_frame, app_instance):
    return GraphUI(parent_frame, app_instance)
