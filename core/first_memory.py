import sqlite3
from pathlib import Path

project_folder = Path(__file__).resolve().parent.parent
database_file = project_folder / "database" / "memory.db"

connection = sqlite3.connect(database_file)

memories = [
    ("The user's preferred name is Kshitiz.", "identity"),
    ("When Kshitiz is recognized, greet him with: Hey, daddy's home!", "greeting")
]

for content, category in memories:
    existing = connection.execute(
        "SELECT id FROM memories WHERE content = ? AND category = ?",
        (content, category)
    ).fetchone()

    if existing is None:
        connection.execute(
            "INSERT INTO memories (content, category) VALUES (?, ?)",
            (content, category)
        )

connection.commit()
connection.close()

print("Kairo saved its first personal memories!")