import os
import sqlite3
import logging
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# Database configuration from environment variables with sensible defaults
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "diabetes_risk_db")

# Path to SQLite fallback database if MySQL is unavailable
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diabetes_risk.db")

_backend_type = None  # "mysql" or "sqlite"

def get_connection():
    """
    Attempt to establish a MySQL connection. If MySQL is unavailable,
    gracefully fallback to SQLite to prevent application crash during development/tests.
    """
    global _backend_type
    
    # Check if force SQLite is requested via env
    if os.environ.get("FORCE_SQLITE", "0") == "1":
        _backend_type = "sqlite"
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"

    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            autocommit=False
        )
        _backend_type = "mysql"
        return conn, "mysql"
    except Exception as mysql_err:
        logger.warning(
            f"MySQL connection to {DB_HOST}:{DB_PORT}/{DB_NAME} failed ({mysql_err}). "
            f"Falling back to local SQLite database: {SQLITE_DB_PATH}"
        )
        _backend_type = "sqlite"
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"


def init_db():
    """
    Ensure the users table exists in the active database backend.
    """
    conn, backend = get_connection()
    try:
        cursor = conn.cursor()
        if backend == "mysql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    age INT NULL,
                    gender VARCHAR(20) NULL,
                    phone VARCHAR(20) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    pregnancies INT NOT NULL DEFAULT 0,
                    glucose FLOAT NOT NULL,
                    blood_pressure FLOAT NOT NULL,
                    skin_thickness FLOAT NOT NULL DEFAULT 0,
                    insulin FLOAT NOT NULL DEFAULT 0,
                    bmi FLOAT NOT NULL,
                    diabetes_pedigree_function FLOAT NOT NULL,
                    age INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_health_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            conn.commit()
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    age INTEGER NULL,
                    gender TEXT NULL,
                    phone TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON users(email);")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    pregnancies INTEGER NOT NULL DEFAULT 0,
                    glucose REAL NOT NULL,
                    blood_pressure REAL NOT NULL,
                    skin_thickness REAL NOT NULL DEFAULT 0,
                    insulin REAL NOT NULL DEFAULT 0,
                    bmi REAL NOT NULL,
                    diabetes_pedigree_function REAL NOT NULL,
                    age INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_user ON health_data(user_id);")
            conn.commit()
        cursor.close()
    finally:
        conn.close()


def _adapt_query(query: str, backend: str) -> str:
    """Adapts query placeholders for SQLite if needed."""
    if backend == "sqlite":
        # Replace %s placeholders with ? for sqlite3
        return query.replace("%s", "?")
    return query


def query_one(query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
    """Execute a query and fetch a single row as a dictionary."""
    conn, backend = get_connection()
    try:
        adapted_query = _adapt_query(query, backend)
        if backend == "mysql":
            cursor = conn.cursor(dictionary=True)
            cursor.execute(adapted_query, params)
            row = cursor.fetchone()
            cursor.close()
            return row
        else:
            cursor = conn.cursor()
            cursor.execute(adapted_query, params)
            row = cursor.fetchone()
            result = dict(row) if row else None
            cursor.close()
            return result
    finally:
        conn.close()


def query_all(query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    """Execute a query and fetch all rows as a list of dictionaries."""
    conn, backend = get_connection()
    try:
        adapted_query = _adapt_query(query, backend)
        if backend == "mysql":
            cursor = conn.cursor(dictionary=True)
            cursor.execute(adapted_query, params)
            rows = cursor.fetchall()
            cursor.close()
            return rows or []
        else:
            cursor = conn.cursor()
            cursor.execute(adapted_query, params)
            rows = cursor.fetchall()
            results = [dict(r) for r in rows] if rows else []
            cursor.close()
            return results
    finally:
        conn.close()


def execute_commit(query: str, params: Tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE query and return the lastrowid or affected rows."""
    conn, backend = get_connection()
    try:
        adapted_query = _adapt_query(query, backend)
        cursor = conn.cursor()
        cursor.execute(adapted_query, params)
        last_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        return last_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
