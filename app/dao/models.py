from database import get_connection

def add_user(email, username, phone, profile_picture, password):
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO users (email, username, phone, profile_picture, password)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, username, phone, profile_picture, password))

def get_user_by_email(email):
    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM users WHERE email = ?
        ''', (email,))
        return cursor.fetchone()

