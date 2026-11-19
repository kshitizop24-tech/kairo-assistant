from pathlib import Path

project_folder = Path(__file__).resolve().parent.parent
memory_file = project_folder / "database" / "notes.txt"

with memory_file.open("a", encoding="utf-8") as file:
    file.write("\nKairo was here")

print("Kairo successfully wrote to its local memory!")
print("Updated memory:")
print(memory_file.read_text(encoding="utf-8"))