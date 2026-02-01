import math
import random

class Node:
    def __init__(self, uid, label, group="default", x=0, y=0, radius=20):
        self.uid = uid
        self.label = label
        self.group = group  # 'host', 'service'
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.radius = radius
        self.fixed = False  # If dragged, it becomes fixed temporarily

class Edge:
    def __init__(self, source_uid, target_uid, length=100):
        self.source_uid = source_uid
        self.target_uid = target_uid
        self.length = length

class GraphSimulation:
    def __init__(self, width=800, height=600):
        self.nodes = {}
        self.edges = []
        self.width = width
        self.height = height
        
        # Physics constants
        self.repulsion = 5000
        self.spring_k = 0.05
        self.damping = 0.85
        self.dt = 0.5 # Time step

    def add_node(self, node):
        self.nodes[node.uid] = node

    def add_edge(self, edge):
        self.edges.append(edge)

    def clear(self):
        self.nodes = {}
        self.edges = []

    def step(self):
        """Perform one step of physics simulation."""
        
        # 1. Repulsion (Node vs Node)
        node_ids = list(self.nodes.keys())
        for i in range(len(node_ids)):
            n1 = self.nodes[node_ids[i]]
            if n1.fixed: continue
            
            fx, fy = 0, 0
            for j in range(len(node_ids)):
                if i == j: continue
                n2 = self.nodes[node_ids[j]]
                
                dx = n1.x - n2.x
                dy = n1.y - n2.y
                dist_sq = dx*dx + dy*dy
                dist = math.sqrt(dist_sq)
                
                if dist < 1: dist = 1 # Avoid div by zero
                
                # Coulomb's law: F = k / r^2
                # Vector direction: dx/dist, dy/dist
                force = self.repulsion / (dist_sq + 0.1)
                fx += (dx / dist) * force
                fy += (dy / dist) * force
            
            n1.vx += fx * self.dt
            n1.vy += fy * self.dt

        # 2. Attraction (Springs)
        for edge in self.edges:
            if edge.source_uid not in self.nodes or edge.target_uid not in self.nodes:
                continue
                
            n1 = self.nodes[edge.source_uid]
            n2 = self.nodes[edge.target_uid]
            
            dx = n1.x - n2.x
            dy = n1.y - n2.y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < 1: dist = 1
            
            # Spring force: F = k * (current_len - target_len)
            force = (dist - edge.length) * self.spring_k
            
            fx = (dx / dist) * force
            fy = (dy / dist) * force
            
            if not n1.fixed:
                n1.vx -= fx * self.dt
                n1.vy -= fy * self.dt
            if not n2.fixed:
                n2.vx += fx * self.dt
                n2.vy += fy * self.dt

        # 3. Center Gravity (keep visible) & Update Position
        cx, cy = self.width / 2, self.height / 2
        for uid, node in self.nodes.items():
            if node.fixed: continue
            
            # Weak gravity to center
            dx = node.x - cx
            dy = node.y - cy
            node.vx -= dx * 0.005
            node.vy -= dy * 0.005
            
            # Update pos
            node.x += node.vx * self.dt
            node.y += node.vy * self.dt
            
            # Damping
            node.vx *= self.damping
            node.vy *= self.damping
            
            # Boundary (Walls) - Optional, bounce back
            margin = 50
            if node.x < margin: node.vx += 1
            if node.x > self.width - margin: node.vx -= 1
            if node.y < margin: node.vy += 1
            if node.y > self.height - margin: node.vy -= 1
