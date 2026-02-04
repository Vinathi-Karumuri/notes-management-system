import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "notes.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

conn = sqlite3.connect(DB_PATH)

with open(SCHEMA_PATH, "r") as f:
    conn.executescript(f.read())

conn.commit()
conn.close()

print("Database initialized successfully")