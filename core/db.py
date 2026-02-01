import sqlite3
import os
from datetime import datetime
import logging

logger = logging.getLogger("redboar")

DEFAULT_DB_PATH = os.path.join(os.path.expanduser("~"), ".config", "redboar", "redboar.db")

def _init_db_connection(db_path=None):
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_schema(db_path=None):
    """Initializes the database schema."""
    conn = _init_db_connection(db_path)
    cursor = conn.cursor()
    
    # Projects table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at TEXT
    )
    ''')
    
    # Hosts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hosts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        ip_address TEXT,
        hostname TEXT,
        os_name TEXT,
        status TEXT,
        UNIQUE(project_id, ip_address),
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')
    
    # Services table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        host_id INTEGER NOT NULL,
        port INTEGER,
        protocol TEXT,
        service_name TEXT,
        product TEXT,
        version TEXT,
        state TEXT,
        UNIQUE(host_id, port, protocol),
        FOREIGN KEY(host_id) REFERENCES hosts(id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database schema initialized at {db_path or DEFAULT_DB_PATH}")

def get_connection(db_path=None):
    """Returns a connection object to the database."""
    return _init_db_connection(db_path)
