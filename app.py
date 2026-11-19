
import streamlit as st
import ollama
import sqlite3
import time
import base64
import uuid
from pathlib import Path
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from core.learning import init_lessons_table, save_lesson, build_lessons_prompt

# --------------------------------
# PAGE SETTINGS
# --------------------------------

st.set_page_config(
    page_title="Kairo",
    page_icon="🐶",
    layout="centered"
)

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"

LOGO_PATH = ASSETS_DIR / "kairo_logo.png"
BACKGROUND_PATH = ASSETS_DIR / "kairo_background.png"
DB_PATH = BASE_DIR / "kairo.db"

GEMINI_MODEL = "gemini-3.5-flash"

# --------------------------------
# DATABASE SETUP + MIGRATION
# --------------------------------

def initialize_database():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(chats)")
    columns = [column[1] for column in cursor.fetchall()]

    if "response_time" not in columns:
        cursor.execute(
            "ALTER TABLE chats ADD COLUMN response_time REAL"
        )

    if "model_name" not in columns:
        cursor.execute(
            "ALTER TABLE chats ADD COLUMN model_name TEXT"
        )

    if "conversation_id" not in columns:
        cursor.execute(
            "ALTER TABLE chats ADD COLUMN conversation_id TEXT"
        )

    # Preserve old messages by placing them into
    # one conversation for each existing user.
    cursor.execute("""
        SELECT DISTINCT user_name
        FROM chats
        WHERE conversation_id IS NULL
    """)

    old_users = cursor.fetchall()

    for row in old_users:
        old_user = row[0]
        conversation_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO conversations (id, user_name, title)
            VALUES (?, ?, ?)
        """, (
            conversation_id,
            old_user,
            "Previous chats"
        ))

        cursor.execute("""
            UPDATE chats
            SET conversation_id = ?
            WHERE LOWER(user_name) = LOWER(?)
            AND conversation_id IS NULL
        """, (
            conversation_id,
            old_user
        ))

    connection.commit()
    connection.close()


initialize_database()
init_lessons_table()

# --------------------------------
# DATABASE FUNCTIONS
# --------------------------------

def create_conversation(user_name):
    conversation_id = str(uuid.uuid4())

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO conversations (id, user_name, title)
        VALUES (?, ?, ?)
    """, (
        conversation_id,
        user_name,
        "New Chat"
    ))

    connection.commit()
    connection.close()

    return conversation_id


def get_conversations(user_name):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, title, updated_at
        FROM conversations
        WHERE LOWER(user_name) = LOWER(?)
        ORDER BY updated_at DESC
    """, (user_name,))

    rows = cursor.fetchall()
    connection.close()

    return [
        {
            "id": row[0],
            "title": row[1],
            "updated_at": row[2]
        }
        for row in rows
    ]


def rename_conversation(conversation_id, new_title):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE conversations
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        new_title,
        conversation_id
    ))

    connection.commit()
    connection.close()


def delete_conversation(conversation_id):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM chats WHERE conversation_id = ?",
        (conversation_id,)
    )
    cursor.execute(
        "DELETE FROM conversations WHERE id = ?",
        (conversation_id,)
    )

    connection.commit()
    connection.close()


def save_message(
    user_name,
    conversation_id,
    role,
    message,
    response_time=None,
    model_name=None
):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO chats
        (
            user_name,
            conversation_id,
            role,
            message,
            response_time,
            model_name
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_name,
        conversation_id,
        role,
        message,
        response_time,
        model_name
    ))

    cursor.execute("""
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (conversation_id,))

    connection.commit()
    connection.close()


def load_messages(conversation_id):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT role, message, response_time, model_name
        FROM chats
        WHERE conversation_id = ?
        ORDER BY id ASC
    """, (conversation_id,))

    rows = cursor.fetchall()
    connection.close()

    return [
        {
            "role": row[0],
            "content": row[1],
            "response_time": row[2],
            "model_name": row[3]
        }
        for row in rows
    ]


# --------------------------------
# GEMINI CONNECTION
# --------------------------------

def get_gemini_client():
    return genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"]
    )


# --------------------------------
# KAIRO IDENTITY
# --------------------------------

def get_system_prompt(user_name):
    return f"""
    Your name is Kairo.

    You are currently assisting {user_name}.

    Your identity is Kairo.
    You are a personal AI assistant.

    You should:
    - Be warm and caring toward the user.
    - Communicate naturally.
    - Give clear and accurate answers.
    - Be helpful, intelligent, logical and respectful.
    - Admit when you don't know something.
    - Help the user with projects and tasks.
    - Address the user by their name when appropriate.

    You are operating as Kairo through the selected AI model.
    """


# --------------------------------
# GENERATE OLLAMA RESPONSE
# --------------------------------
def format_duration(seconds):
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"

def generate_ollama_response(messages, user_name, model_name="llama3.1:8b"):
    ###  Find saved lessons that match the latest question  ###
    latest_question = messages[-1]["content"] if messages else ""
    lessons_text = build_lessons_prompt(user_name, latest_question) 
    ollama_history = [
        {
            "role": message["role"],
            "content": message["content"]
        }
        for message in messages
    ]

    stream = ollama.chat(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": get_system_prompt(user_name) + "\n" + lessons_text
            },
            *ollama_history
        ],
        stream=True,
            think=any(name in model_name for name in ["deepseek-r1", "qwen3", "reasoning"])
   )

    shown_thinking = False

    for chunk in stream:
        message = chunk["message"]

        thinking_text = message.get("thinking") or ""
        content_text = message.get("content") or ""

        if thinking_text:
            yield thinking_text
            shown_thinking = True

        if content_text:
            if shown_thinking:
                yield "\n\n---\n\n"
                shown_thinking = False
            yield content_text


# --------------------------------
# GENERATE GEMINI RESPONSE
# --------------------------------

def generate_gemini_response(messages, user_name):
    client = get_gemini_client()

    gemini_history = []

    for message in messages:
        gemini_role = (
            "model"
            if message["role"] == "assistant"
            else "user"
        )

        gemini_history.append({
            "role": gemini_role,
            "parts": [
                {"text": message["content"]}
            ]
        })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=gemini_history,
        config=types.GenerateContentConfig(
            system_instruction=get_system_prompt(user_name)
        )
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    return response.text
def get_backup_model(primary_model):
    if primary_model == "Ollama (Local)":
        return "Gemini"
    else:
        return "Ollama (Local)"

# --------------------------------
# BACKGROUND IMAGE
# --------------------------------

if BACKGROUND_PATH.exists():
    with open(BACKGROUND_PATH, "rb") as image_file:
        encoded_background = base64.b64encode(
            image_file.read()
        ).decode()

    background_css = f"""
    background-image:
        linear-gradient(
            rgba(0, 0, 0, 0.15),
            rgba(0, 0, 0, 0.25)
        ),
        url("data:image/png;base64,{encoded_background}");
    """
else:
    background_css = "background-color: #202020;"


# --------------------------------
# CUSTOM DESIGN
# --------------------------------

st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
    {background_css}
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}

[data-testid="stHeader"] {{
    background: transparent;
}}

[data-testid="stToolbar"] {{
    right: 1rem;
}}

[data-testid="stMain"] {{
    background: transparent;
}}

.block-container {{
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 950px;
}}

[data-testid="stChatMessage"] {{
    background: rgba(20, 20, 20, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 14px;
    backdrop-filter: blur(12px);
}}

[data-testid="stChatInput"] {{
    background: rgba(25, 25, 25, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 14px;
}}

[data-testid="stChatInput"] textarea {{
    color: white;
}}

.stTextInput input {{
    background: rgba(25, 25, 25, 0.8);
    color: white;
    border-radius: 10px;
}}

.stButton button,
.stFormSubmitButton button {{
    background: #b94d35;
    color: white;
    border: none;
    border-radius: 10px;
}}

.stButton button:hover,
.stFormSubmitButton button:hover {{
    background: #d16a4e;
    color: white;
}}

[data-testid="stCaptionContainer"] {{
    color: #eeeeee;
}}
[data-testid="stBottom"] {{
    padding-top: 0;
    padding-bottom: 0;
}}

[data-testid="stBottomBlockContainer"] {{
    padding-top: 0.25rem;
    padding-bottom: 0.25rem;
}}
</style>
""", unsafe_allow_html=True)


# --------------------------------
# LOGO DISPLAY
# --------------------------------

def show_logo():
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=190)
    else:
        st.title("KAIRO 🤖")


# --------------------------------
# SESSION STATE
# --------------------------------

defaults = {
    "user_name": None,
    "messages": [],
    "active_conversation_id": None,
    "show_daddy_greeting": False,
    "show_all_chats": False,
    "pending_fallback": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# --------------------------------
# USER IDENTIFICATION
# --------------------------------

if not st.session_state.user_name:

    show_logo()

    st.subheader("Welcome!")
    st.write("Who's using Kairo today?")

    with st.form("user_identification"):
        name = st.text_input("Enter your name")
        submitted = st.form_submit_button("Enter Kairo")

        if submitted:
            if name.strip():
                st.session_state.user_name = name.strip()

                conversations = get_conversations(
                    name.strip()
                )

                if conversations:
                    st.session_state.active_conversation_id = (
                        conversations[0]["id"]
                    )
                    st.session_state.messages = load_messages(
                        conversations[0]["id"]
                    )
                else:
                    new_id = create_conversation(name.strip())

                    st.session_state.active_conversation_id = new_id
                    st.session_state.messages = []

                st.session_state.show_daddy_greeting = True
                st.rerun()

            else:
                st.warning("Please enter your name.")

    st.stop()


# --------------------------------
# PERSONALIZED GREETINGS
# --------------------------------

greetings = {
    "kshitiz": "kaam karle bkl 🎉",
}

user = st.session_state.user_name.strip().lower()

greeting = greetings.get(
    user,
    f"Welcome to Kairo, {st.session_state.user_name}! 🤖"
)


# --------------------------------
# SIDEBAR
# --------------------------------

with st.sidebar:

    st.title("🤖 Kairo")

    st.caption(
        f"User: {st.session_state.user_name}"
    )

    st.divider()

    # MODEL SELECTOR

    st.subheader("Control Centre")

    model_choice = st.selectbox(
        "Choose AI Model",
        [
            "Ollama (Local)",
            "Gemini",
            "llama3.1:8b",
            "deepseek-r1:14b",
            "deepseek-r1:8b",
            "qwen3:8b",
            "phi4:latest",
            "phi4-reasoning"
        ]
    )

    st.caption(f"Active Model: {model_choice}")

    st.divider()

    # NEW CHAT

    if st.button("＋ New Chat", use_container_width=True):

        new_id = create_conversation(
            st.session_state.user_name
        )

        st.session_state.active_conversation_id = new_id
        st.session_state.messages = []

        st.rerun()

    # PROJECTS BUTTON

    if st.button("📁 Projects", use_container_width=True):
        st.info("Projects will be added here later.")

    st.divider()

    
    # CONVERSATION LIST
    st.subheader("Your Chats")

    conversations = get_conversations(
        st.session_state.user_name
    )

    search_text = st.text_input(
        "Search conversations",
        placeholder="Find a chat..."
    )

    if search_text:
        visible_conversations = [
            chat for chat in conversations
            if search_text.lower() in chat["title"].lower()
        ]
    else:
        # Show ALL conversations, newest first
        visible_conversations = conversations

    if not visible_conversations:
        st.caption("No conversations found.")

    for chat in visible_conversations:
        is_active = (
            chat["id"] ==
            st.session_state.active_conversation_id
        )

        button_label = (
            f"● {chat['title']}"
            if is_active
            else chat["title"]
        )

        if st.button(
            button_label,
            key=f"chat_{chat['id']}",
            use_container_width=True
        ):
            st.session_state.active_conversation_id = chat["id"]

            st.session_state.messages = load_messages(
                chat["id"]
            )

            st.rerun()

           
       

    # RENAME CURRENT CHAT

    with st.expander("✏️ Rename current chat"):

        current_title = next(
            (
                chat["title"]
                for chat in conversations
                if chat["id"] ==
                st.session_state.active_conversation_id
            ),
            "New Chat"
        )

        new_title = st.text_input(
            "Conversation name",
            value=current_title,
            key="rename_chat_input"
        )

        if st.button("Save name", use_container_width=True):

            if new_title.strip():
                rename_conversation(
                    st.session_state.active_conversation_id,
                    new_title.strip()
                )

                st.rerun()


# --------------------------------
# MAIN INTERFACE
# --------------------------------

show_logo()

st.caption(
    f"Your personal AI assistant | User: {st.session_state.user_name}"
)

if st.session_state.show_daddy_greeting:
    st.markdown(f"# {greeting}")
    st.session_state.show_daddy_greeting = False

conversations = get_conversations(
    st.session_state.user_name
)

active_chat = next(
    (
        chat for chat in conversations
        if chat["id"] ==
        st.session_state.active_conversation_id
    ),
    None
)

if active_chat:
    title_col, menu_col = st.columns([10, 1])

    with title_col:
        st.subheader(active_chat["title"])

    with menu_col:
        with st.popover("⋮"):
            if st.button("Delete this chat", key="delete_current_chat"):
                delete_conversation(st.session_state.active_conversation_id)

                remaining = get_conversations(st.session_state.user_name)

                if remaining:
                    st.session_state.active_conversation_id = remaining[0]["id"]
                    st.session_state.messages = load_messages(remaining[0]["id"])
                else:
                    new_id = create_conversation(st.session_state.user_name)
                    st.session_state.active_conversation_id = new_id
                    st.session_state.messages = []

                st.rerun()


# --------------------------------
# DISPLAY CURRENT CHAT ONLY
# --------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])

        if message["role"] == "assistant":

            model_name = message.get("model_name")

            if model_name:
                st.caption(f"🤖 Model: {model_name}")

            elapsed = message.get("response_time")

            if elapsed is not None:
                st.caption(f"⏱ {format_duration(elapsed)}")
                       
             # --- LEARNING: correction box ---
            message_index = st.session_state.messages.index(message)
            correction_key = f"correction_{message_index}"
            with st.expander("✏️ Teach Kairo a correction"):
                correct_answer = st.text_area(
                    "What should the correct answer be?",
                    key=f"{correction_key}_text"
                )
                if st.button("Save lesson", key=f"{correction_key}_save"):
                    if correct_answer.strip():
                         # Find the question that came just before this reply
                        question_text = ""
                        if message_index > 0:
                            question_text = st.session_state.messages[message_index - 1]["content"]

                        save_lesson(
                            st.session_state.user_name,
                            question_text,
                            message["content"],
                            correct_answer.strip()
                        )
                        st.success("Lesson saved. Kairo will remember it.")
                    else:
                        st.warning("Type the correct answer first.")


# --------------------------------
# MODEL FALLBACK APPROVAL
# --------------------------------

if st.session_state.pending_fallback:

    fallback = st.session_state.pending_fallback

    st.warning(
        f"{fallback['failed_model']} is unavailable. "
        f"Would you like Kairo to switch to "
        f"{fallback['backup_model']}?"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            f"Switch to {fallback['backup_model']}",
            key="approve_fallback"
        ):
            st.session_state.pending_fallback["approved"] = True
            st.rerun()

    with col2:
        if st.button(
            "Keep current model",
            key="decline_fallback"
        ):
            st.session_state.pending_fallback = None
            st.info("Keeping your current model.")
# --------------------------------
# CHAT INPUT
# --------------------------------

if prompt := st.chat_input("Talk to Kairo..."):

    user_message = {
        "role": "user",
        "content": prompt
    }

    st.session_state.messages.append(user_message)

    save_message(
        st.session_state.user_name,
        st.session_state.active_conversation_id,
        "user",
        prompt
    )

    with st.chat_message("user"):
        st.markdown(prompt)

   
    # --------------------------------
    # KAIRO RESPONSE + LIVE TIMER
    # --------------------------------
    try:
        with st.chat_message("assistant"):
            timer_placeholder = st.empty()
            response_placeholder = st.empty()
            start_time = time.perf_counter()

            with timer_placeholder.container():
                components.html(
                    """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <style>
                            body {
                                margin: 0;
                                padding: 4px 0;
                                background: transparent;
                                font-family: sans-serif;
                                color: #ddd;
                                font-size: 13px;
                            }
                            .timer {
                                display: flex;
                                align-items: center;
                                gap: 6px;
                            }
                            .dot {
                                color: #22c55e;
                                font-size: 11px;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="timer">
                            <span class="dot">●</span>
                            <span>Thinking about you...</span>
                            <span>·</span>
                            <span id="timer">00:00.0</span>
                        </div>
                        <script>
                            const start = performance.now();
                                                       function updateTimer() {
                                const elapsed =
                                    (performance.now() - start) / 1000;
                                const hours =
                                    Math.floor(elapsed / 3600);
                                const minutes =
                                    Math.floor((elapsed % 3600) / 60);
                                const seconds =
                                    Math.floor(elapsed % 60);

                                let text;
                                if (hours > 0) {
                                    text = hours + "h " +
                                        String(minutes).padStart(2, "0") + "m " +
                                        String(seconds).padStart(2, "0") + "s";
                                } else if (minutes > 0) {
                                    text = minutes + "m " +
                                        String(seconds).padStart(2, "0") + "s";
                                } else {
                                    text = elapsed.toFixed(1) + "s";
                                }

                                document.getElementById("timer")
                                    .textContent = text;
                            }
                            updateTimer();
                            setInterval(updateTimer, 100);
                        </script>
                    </body>
                    </html>
                    """,
                    height=25,
                    scrolling=False
                )

            reply = ""

             # MODEL ROUTING
            if model_choice != "Gemini":
                # Default option uses llama3.1:8b; other choices use their own name
                ollama_model = "llama3.1:8b" if model_choice == "Ollama (Local)" else model_choice

                for chunk in generate_ollama_response(
                    st.session_state.messages,
                    st.session_state.user_name,
                    ollama_model
                ):
                    reply += chunk
                    response_placeholder.markdown(reply + "▌")

                actual_model = f"Ollama ({ollama_model})"


            elif model_choice == "Gemini":
                reply = generate_gemini_response(
                    st.session_state.messages,
                    st.session_state.user_name
                )
                response_placeholder.markdown(reply)
                actual_model = f"Gemini ({GEMINI_MODEL})"

            # RESPONSE TIME
            end_time = time.perf_counter()
            response_time = end_time - start_time

            timer_placeholder.empty()
            response_placeholder.markdown(reply)

            st.caption(f"🤖 Model: {actual_model}")
            st.caption(f"⏱ {format_duration(response_time)}")

        # SAVE AI RESPONSE
        assistant_message = {
            "role": "assistant",
            "content": reply,
            "response_time": response_time,
            "model_name": actual_model
        }

        st.session_state.messages.append(assistant_message)

        save_message(
            st.session_state.user_name,
            st.session_state.active_conversation_id,
            "assistant",
            reply,
            response_time,
            actual_model
        )

    except Exception as e:        
        print("KAIRO ERROR:", repr(e))
        backup_model = get_backup_model(model_choice)

        st.session_state.pending_fallback = {
            "failed_model": model_choice,
            "backup_model": backup_model,
            "error": str(e),
            "approved": False
        }

        st.rerun()
