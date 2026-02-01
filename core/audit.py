import logging
import json
from datetime import datetime
from . import db

logger = logging.getLogger("redboar")

class AuditLogger:
    """Helper class to log events to the project timeline."""
    
    @staticmethod
    def log(project_id, category, message, details=None):
        """
        Logs an event to the timeline table.
        
        Args:
            project_id (int): ID of the active project.
            category (str): Category (SCAN, SYSTEM, NOTE, REPORT, PAYLOAD).
            message (str): Succinct description of the event.
            details (str/dict): Optional blob of extra info.
        """
        if not project_id:
            logger.warning("AuditLogger: No project_id provided, skipping log.")
            return

        try:
            timestamp = datetime.now().isoformat()
            
            if isinstance(details, (dict, list)):
                details = json.dumps(details)
                
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO timeline (project_id, timestamp, category, message, details)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, timestamp, category, message, details))
            conn.commit()
            conn.close()
            
            logger.debug(f"Audit Logged: [{category}] {message}")
            
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")
