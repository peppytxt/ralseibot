# =====================
# === File: utils/database.py
# =====================
import sqlite3
from config import DB_PATH

# Função simples para obter conexão (singleton por módulo)
_conn = None

def get_db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        last_xp REAL DEFAULT 0
    )
    """)
    conn.commit()

# inicializa ao importar
init_db()