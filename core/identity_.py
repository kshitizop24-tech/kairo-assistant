
import sqlite3
import re
from pathlib import Path

# Locate the main Kairo project folder
project_folder = Path(__file__).resolve().parent.parent

# Locate the memory database
database_file = project_folder / "database" / "memory.db"

# Connect to the database
connection = sqlite3.connect(database_file)

# Retrieve saved identity memory
result = connection.execute(
    "SELECT content FROM memories WHERE category = 'identity'"
).fetchone()

# Close database connection
connection.close()

print("Welcome to Kairo!")

# Identity recognition loop

# Identity recognition loop
while True:
    name = input("Who's using Kairo? ").strip()

    if not name:
        print("Please enter your name.")
        continue

    if name.casefold() == "kshitiz":
        print("\nyaaaay, daddy's home!")
        break

    print("\nIdentity not recognized. Please try again.")

