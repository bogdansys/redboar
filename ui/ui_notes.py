import tkinter as tk
from tkinter import ttk, messagebox
import os
import logging

logger = logging.getLogger("redboar")

class NotesUI:
    def __init__(self, parent_frame, app_instance):
        self.app = app_instance
        self.parent = parent_frame
        
        self.setup_ui()
        
    def setup_ui(self):
        # Toolbar
        tb = ttk.Frame(self.parent, padding=5)
        tb.pack(fill="x", side="top")
        
        ttk.Button(tb, text="Save Notes", command=self.save_notes).pack(side="left", padx=5)
        ttk.Button(tb, text="Reload", command=self.load_notes).pack(side="left", padx=5)
        ttk.Label(tb, text="(Saved to project directory)", foreground="grey").pack(side="left", padx=10)

        # Editor
        self.text_area = tk.Text(self.parent, wrap="word", font=("Consolas", 11), undo=True)
        self.text_area.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Initial load
        # Delay slightly to let state load
        self.parent.after(500, self.load_notes)

    def get_notes_path(self):
        proj_id = self.app.state_manager.current_project_id
        if not proj_id: return None
        
        # We need a project directory. 
        # Currently StateManager tracks ID. Let's assume a "notes" storage 
        # relative to the DB or just in typical User Docs for now.
        # Actually, let's store it in Documents/redboar_projects/<id>/notes.md
        
        base_dir = os.path.join(os.path.expanduser("~"), "Documents", "redboar_projects")
        proj_dir = os.path.join(base_dir, str(proj_id))
        os.makedirs(proj_dir, exist_ok=True)
        return os.path.join(proj_dir, "notes.md")

    def load_notes(self):
        path = self.get_notes_path()
        if not path:
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", "Open a project to take notes.")
            self.text_area.config(state="disabled")
            return

        self.text_area.config(state="normal")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.text_area.delete("1.0", "end")
                self.text_area.insert("1.0", content)
            except Exception as e:
                logger.error(f"Failed to load notes: {e}")
        else:
            # New notes
            pass

    def save_notes(self):
        path = self.get_notes_path()
        if not path: return
        
        content = self.text_area.get("1.0", "end-1c")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Notes", "Notes saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save notes: {e}")

def create_ui(parent_frame, app_instance):
    return NotesUI(parent_frame, app_instance)
