"""
Streamlit chat interface for the OpenAI Assistant **asst_i9gadw6w4Xd0swmScH5jH4Pv**
with light CGIAR‑inspired branding.

Run locally with:
    pip install streamlit openai python-dotenv
    streamlit run cgair_chat_streamlit.py

Set an environment variable *OPENAI_API_KEY* or paste the key into the sidebar.
"""

import json
import datetime
import time
from pathlib import Path
import os
from dotenv import load_dotenv

import streamlit as st
from openai import OpenAI

# Load environment variables
load_dotenv()

###############################################################################
# --- PAGE CONFIG & GLOBAL STYLE ------------------------------------------- #
###############################################################################

st.set_page_config(
    page_title="CGIAR AI Assistant Chat",
    page_icon="🌾",
    layout="wide",
)

CGIAR_GREEN = "#2E7D32"  # primary CGIAR brand colour per 2012 toolkit
CGIAR_BLUE = "#1A4D8F"   # secondary colour used on cgiar.org
LOGO_URL = "logo.png"

st.markdown(
    f"""
    <style>
        /* Hide Streamlit default menu/footer */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* Chat bubbles */
        .chat-bubble {{
            padding: 0.75rem 1rem;
            border-radius: 0.75rem;
            margin-bottom: 0.5rem;
            line-height: 1.45;
        }}
        .user-bubble {{
            background-color: {CGIAR_GREEN}20;
            color: {CGIAR_GREEN};
        }}
        .assistant-bubble {{
            background-color: {CGIAR_BLUE}10;
            color: {CGIAR_BLUE};
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

###############################################################################
# --- SIDEBAR: SETTINGS ----------------------------------------------------- #
###############################################################################

with st.sidebar:
    st.image(LOGO_URL, width=160)
    st.header("Settings")

    assistant_id = "asst_i9gadw6w4Xd0swmScH5jH4Pv"  # hardcoded ID
    
    # Download button in sidebar
    data = {
        "assistant_id": assistant_id,
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "messages": st.session_state.messages if "messages" in st.session_state else []
    }
    json_bytes = json.dumps(data, indent=2).encode("utf-8")
    st.download_button(
        label="💾 Download conversation",
        data=json_bytes,
        file_name="chat_history.json",
        mime="application/json",
    )

###############################################################################
# --- INITIALISE CLIENT & SESSION STATE ------------------------------------ #
###############################################################################

def get_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("Please set the OPENAI_API_KEY environment variable ✨")
        return None
    return OpenAI(api_key=api_key)


def ensure_thread(client: OpenAI, assistant_id: str) -> str:
    """Return an existing thread_id or create a new one and store it."""
    if "thread_id" in st.session_state:
        return st.session_state.thread_id
    
    # Create a new thread
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id
    
    # If we have existing messages, add them to the new thread
    if "messages" in st.session_state:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=msg["content"]
                )
    
    return thread.id


if "messages" not in st.session_state:
    st.session_state.messages = []  # each item: {"role": "user"|"assistant", "content": str}

###############################################################################
# --- OPENAI ASSISTANT WRAPPER --------------------------------------------- #
###############################################################################

def call_assistant(user_text: str) -> str:
    """Send *user_text* to the Assistant and return its reply."""
    client = get_client()
    if client is None:
        return ""

    # Ensure a thread exists for this chat session
    thread_id = ensure_thread(client, assistant_id)

    # Push user message to thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_text
    )

    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    # Poll until completion (with tiny back‑off)
    while run.status not in {"completed", "failed", "cancelled", "expired"}:
        time.sleep(0.5)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

    if run.status != "completed":
        return f"⚠️ Assistant run ended with status **{run.status}**."

    # Fetch all messages and return the latest assistant response
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
    if messages.data:
        return messages.data[0].content[0].text.value
    return "(No assistant response)"

###############################################################################
# --- MAIN CHAT UI ---------------------------------------------------------- #
###############################################################################

st.title("CGIAR AI Assistant")

chat_placeholder = st.container()

# Display previous messages
for msg in st.session_state.messages:
    bubble_class = "user-bubble" if msg["role"] == "user" else "assistant-bubble"
    chat_placeholder.markdown(
        f'<div class="chat-bubble {bubble_class}"><b>{"You" if msg["role"]=="user" else "Assistant"}:</b> {msg["content"]}</div>',
        unsafe_allow_html=True,
    )

# Chat input (uses Streamlit 1.27+)
user_input = st.chat_input("Type your message and press Enter…")

if user_input:
    # 1️⃣  Add user message to local history
    st.session_state.messages.append({"role": "user", "content": user_input})
    chat_placeholder.markdown(
        f'<div class="chat-bubble user-bubble"><b>You:</b> {user_input}</div>',
        unsafe_allow_html=True,
    )

    # 2️⃣  Call assistant and stream response token by token
    with st.spinner("Assistant is composing a reply…"):
        assistant_reply = call_assistant(user_input)

    # 3️⃣  Add assistant reply to history
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    chat_placeholder.markdown(
        f'<div class="chat-bubble assistant-bubble"><b>Assistant:</b> {assistant_reply}</div>',
        unsafe_allow_html=True,
    )
