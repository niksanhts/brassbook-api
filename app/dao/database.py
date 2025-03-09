import sqlite3

def get_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к столбцам по имени
    return conn

def create_users_table():
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL UNIQUE,
                profile_picture TEXT,
                password TEXT NOT NULL
            )
        ''')
