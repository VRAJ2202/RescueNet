# storage.py
import sqlite3
import json

class MessageStore:
    def __init__(self, db_path="rescuenet.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                sender_id TEXT,
                type TEXT,
                priority TEXT,
                timestamp INTEGER,
                ttl INTEGER,
                payload TEXT
            )
        """)
        self.conn.commit()

    def save_message(self, msg):
        self.conn.execute("""
            INSERT OR IGNORE INTO messages
            (message_id, sender_id, type, priority, timestamp, ttl, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            msg["message_id"], msg["sender_id"], msg["type"], msg["priority"],
            msg["timestamp"], msg["ttl"], json.dumps(msg["payload"])
        ))
        self.conn.commit()

    def message_exists(self, message_id):
        cur = self.conn.execute("SELECT 1 FROM messages WHERE message_id = ?", (message_id,))
        return cur.fetchone() is not None