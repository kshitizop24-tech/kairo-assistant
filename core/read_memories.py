import sqlite3
from pathlib import Path

project_folder = Path(__file__).resolve().parent.parent
database_file = project_folder / "database" / "memory.db"

connection = sqlite3.connect(database_file)

memories = connection.execute(
    "SELECT id, content, category FROM memories"
).fetchall()

print("\n--- KAIRO'S STORED MEMORIES ---")

for memory in memories:
    print(f"\nID: {memory[0]}")
    print(f"Memory: {memory[1]}")
    print(f"Category: {memory[2]}")

connection.close()