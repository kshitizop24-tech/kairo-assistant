import sqlite3
from pathlib import Path

project_folder = Path(__file__).resolve().parent.parent
database_file = project_folder / "database" / "memory.db"

connection = sqlite3.connect(database_file)

connection.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

connection.commit()
connection.close()

print("Kairo's local memory database is ready!")