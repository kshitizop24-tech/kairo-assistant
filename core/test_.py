from pathlib import Path

project_folder = Path(__file__).resolve().parent.parent
memory_file = project_folder / "database" / "memory test.txt"

content = memory_file.read_text(encoding="utf-8")

print("Kairo successfully accessed its local memory!")
print("Stored memory:", content)