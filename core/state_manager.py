import os
import sqlite3
import logging
from datetime import datetime
from . import db

logger = logging.getLogger("redboar")

class StateManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StateManager, cls).__new__(cls)
            cls._instance.current_project_id = None
            cls._instance.current_project_name = None
            
            # Ensure DB is ready
            db.init_schema()
        return cls._instance

    def create_project(self, name, description=""):
        """Creates a new project and sets it as active."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            created_at = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)",
                (name, description, created_at)
            )
            project_id = cursor.lastrowid
            conn.commit()
            
            self.set_current_project(project_id, name)
            logger.info(f"Created new project: {name} (ID: {project_id})")
            return project_id
        except Exception as e:
            logger.error(f"Failed to create project '{name}': {e}")
            raise
        finally:
            conn.close()

    def load_project(self, project_id):
        """Loads an existing project by ID."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if row:
                self.set_current_project(project_id, row['name'])
                logger.info(f"Loaded project: {row['name']} (ID: {project_id})")
                return True
            return False
        finally:
            conn.close()

    def get_all_projects(self):
        """Returns a list of all projects (id, name, created_at)."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, name, created_at, description FROM projects ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def set_current_project(self, project_id, name):
        self.current_project_id = project_id
        self.current_project_name = name

    def get_current_project(self):
        return {
            "id": self.current_project_id,
            "name": self.current_project_name
        }
