import os
import re
import sqlite3
from datetime import datetime

# kairo.db is in the main project folder (one level above "core")
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "kairo.db",
)

# Common words we ignore when matching a new question to an old lesson
STOP_WORDS = {
    "the", "and", "for", "are", "was", "what", "who", "how", "why",
    "when", "where", "which", "this", "that", "with", "about", "tell",
    "you", "your", "can", "does", "did", "has", "have", "from", "into",
    "give", "please", "explain", "is", "it", "me", "my", "of", "to", "in",
}


def _connect(db_path=None):
    return sqlite3.connect(db_path or DB_PATH)


def init_lessons_table(db_path=None):
    """Creates the lessons table if it does not exist yet."""
    conn = _connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            question TEXT,
            bad_answer TEXT,
            correction TEXT,
            timestamp TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_lesson(user_name, question, bad_answer, correction, db_path=None):
    """Saves one mistake and its correction."""
    conn = _connect(db_path)
    conn.execute(
        "INSERT INTO lessons (user_name, question, bad_answer, correction, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_name, question, bad_answer, correction,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def _keywords(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


def get_relevant_lessons(user_name, question, limit=3, db_path=None):
    """Finds saved lessons that share keywords with the new question."""
    q_words = _keywords(question)
    if not q_words:
        return []

    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT question, bad_answer, correction FROM lessons WHERE user_name = ?",
        (user_name,),
    ).fetchall()
    conn.close()

    scored = []
    for old_q, bad, fix in rows:
        overlap = len(q_words & _keywords(old_q + " " + fix))
        if overlap > 0:
            scored.append((overlap, old_q, bad, fix))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {"question": q, "bad_answer": b, "correction": c}
        for _, q, b, c in scored[:limit]
    ]


def build_lessons_prompt(user_name, question, db_path=None):
    """Returns a text block to add to Kairo's system prompt.
    Returns an empty string if there are no useful lessons."""
    lessons = get_relevant_lessons(user_name, question, db_path=db_path)
    if not lessons:
        return ""

    text = "Lessons from your past mistakes with this user. Do not repeat them:\n"
    for lesson in lessons:
        text += (
            f"- Question: {lesson['question']}\n"
            f"  You answered wrongly: {lesson['bad_answer'][:200]}\n"
            f"  Correct answer: {lesson['correction']}\n"
        )
    return text


# ---- Quick test: only runs when you run this file directly ----
if __name__ == "__main__":
    test_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_lessons.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    init_lessons_table(test_db)
    save_lesson(
        "Kshitiz",
        "What is the capital of Australia?",
        "The capital of Australia is Sydney.",
        "The capital of Australia is Canberra, not Sydney.",
        db_path=test_db,
    )

    print(build_lessons_prompt("Kshitiz", "Tell me about Australia's capital city", db_path=test_db))
    print("Unrelated question gives:", repr(build_lessons_prompt("Kshitiz", "Explain GDP", db_path=test_db)))

    os.remove(test_db)