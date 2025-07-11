"""
Streamlit chat interface with chart generation capabilities for the OpenAI Assistant
with light CGIAR‑inspired branding.

Run locally with:
    pip install streamlit openai python-dotenv pandas
    streamlit run chart_app.py

Set an environment variable *OPENAI_API_KEY* or paste the key into the sidebar.
"""

import json
import datetime
import time
from pathlib import Path
import os
from dotenv import load_dotenv
import pandas as pd
import re

import streamlit as st
from openai import OpenAI

# Load environment variables
load_dotenv()

###############################################################################
# --- PAGE CONFIG & GLOBAL STYLE ------------------------------------------- #
###############################################################################

st.set_page_config(
    page_title="CGIAR AI Assistant Chat with Charts",
    page_icon="📊",
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
# --- CHART GENERATION FUNCTIONS ------------------------------------------- #
###############################################################################

def extract_chart_data(text):
    """Extract chart data from the assistant's response."""
    # Look for patterns like "Category A: 71" or similar numerical data
    pattern = r'([^:]+):\s*(\d+)'
    matches = re.findall(pattern, text)
    
    if not matches:
        return None, None
        
    try:
        # Convert matches to list of lists
        data = [[label.strip(), int(value)] for label, value in matches]
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(data, columns=['Label', 'Value'])
        return df, str(data)
    except:
        return None, None

def create_bar_chart(df):
    """Create a bar chart using Streamlit."""
    if df is not None:
        # Create a new container for the chart
        chart_container = st.container()
        with chart_container:
            st.subheader("Data Visualization")
            # Create a more visually appealing chart
            chart = st.bar_chart(
                df.set_index('Label'),
                use_container_width=True,
                height=400
            )
            
            # Also display the data in a table format
            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True
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

    # Add chart generation instruction to user's message
    enhanced_prompt = f"""
    {user_text}
    
    If the user's request involves data that could be visualized, please include a bar chart.
    Format the data as a list of lists where each inner list contains [label, value].
    Example: [[\"Category A\", 10], [\"Category B\", 20]]
    """

    # Ensure a thread exists for this chat session
    thread_id = ensure_thread(client, assistant_id)

    # Push user message to thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=enhanced_prompt
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
        # Handle different content types in the response
        message = messages.data[0]
        content_parts = []
        
        for content in message.content:
            if content.type == 'text':
                content_parts.append(content.text.value)
            elif content.type == 'image_file':
                content_parts.append("[Image]")  # Placeholder for image content
                
        return " ".join(content_parts)
    return "(No assistant response)"

###############################################################################
# --- MAIN CHAT UI ---------------------------------------------------------- #
###############################################################################

st.title("CGIAR AI Assistant with Charts")

# Create two columns for chat and charts
col1, col2 = st.columns([2, 1])

with col1:
    chat_placeholder = st.container()
    
    # Display previous messages
    for msg in st.session_state.messages:
        bubble_class = "user-bubble" if msg["role"] == "user" else "assistant-bubble"
        chat_placeholder.markdown(
            f'<div class="chat-bubble {bubble_class}"><b>{"You" if msg["role"]=="user" else "Assistant"}:</b> {msg["content"]}</div>',
            unsafe_allow_html=True,
        )

with col2:
    chart_placeholder = st.container()
    # Display charts for previous messages
    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            df, _ = extract_chart_data(msg["content"])
            if df is not None:
                with chart_placeholder:
                    create_bar_chart(df)

# Chat input at the bottom
user_input = st.chat_input("Type your message and press Enter…")

if user_input:
    # Add user message to local history
    st.session_state.messages.append({"role": "user", "content": user_input})
    with col1:
        st.markdown(
            f'<div class="chat-bubble user-bubble"><b>You:</b> {user_input}</div>',
            unsafe_allow_html=True,
        )

    # Call assistant and stream response token by token
    with st.spinner("Assistant is composing a reply…"):
        assistant_reply = call_assistant(user_input)

    # Add assistant reply to history
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    with col1:
        st.markdown(
            f'<div class="chat-bubble assistant-bubble"><b>Assistant:</b> {assistant_reply}</div>',
            unsafe_allow_html=True,
        )
    
    # Try to extract and display chart data from the response
    df, _ = extract_chart_data(assistant_reply)
    if df is not None:
        with col2:
            create_bar_chart(df) 