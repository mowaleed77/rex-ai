
"""Demo UI: streamlit run apps/streamlit_app.py"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st
from rex.assistant.engine import Session
from rex.assistant.rag import RagAssistant


st.set_page_config(
    page_title="REX AI | Smart Academy",
    page_icon="🎓",
    layout="centered",
)

st.markdown(
    """
    <style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
    [data-testid="stBottom"], [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {
        background-color: #0e1117 !important;
        color: #e5e7eb;
    }

    h1, h2, h3 {
        color: #8ab4f8 !important;
    }

    [data-testid="stCaptionContainer"], .stCaption {
        color: #9ca3af !important;
    }

    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown strong {
        color: #e5e7eb;
    }

    .stChatMessage {
        background-color: #1a1f2b !important;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 12px;
    }

    .stChatMessage p, .stChatMessage li {
        unicode-bidi: plaintext;
        text-align: start;
    }

    [data-testid="stChatInput"] {
        background-color: #1a1f2b !important;
        border-color: #2d3748 !important;
    }

    [data-testid="stChatInput"] textarea {
        color: #f3f4f6 !important;
        -webkit-text-fill-color: #f3f4f6 !important;
        background-color: #1a1f2b !important;
        caret-color: #f3f4f6 !important;
        opacity: 1 !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #9ca3af !important;
        -webkit-text-fill-color: #9ca3af !important;
        opacity: 1 !important;
    }

    [data-testid="stChatInputSubmitButton"] {
        color: #ffffff !important;
    }

    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessageContent"] p {
        color: #e5e7eb !important;
    }

    [data-testid="stSidebar"] {
        background-color: #141824;
        color: #e6e6e6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎓 REX AI | Smart Academy")
st.caption("Your bilingual assistant for academy courses")

if "bot" not in st.session_state:
    st.session_state.bot = RagAssistant()

if "session" not in st.session_state:
    st.session_state.session = Session()

if "messages" not in st.session_state:
    st.session_state.messages = []

bot = st.session_state.bot

with st.sidebar:
    st.markdown("### ⚙️ REX status")

    llm = bot.llm

    if bot.llm_enabled and llm is not None:
        st.success(f"LLM + RAG on - {llm.model}")
    else:
        st.warning("Rule-based mode: LLM is unavailable.")

    st.caption(
        f"{len(bot.retriever.chunks)} knowledge documents loaded"
    )

    st.divider()
    st.markdown("**Supported languages**")
    st.write("English and Arabic")


def show(text):
    """Display a message while preserving line breaks."""
    st.markdown(text.replace("\n", "  \n"))


if not st.session_state.messages:
    st.markdown(
        """
        ### Welcome to REX AI!

        Ask me about courses, prices, duration, prerequisites,
        and career opportunities.

        **مرحباً بك في REX AI!**

        اسألني عن الكورسات والأسعار والمدة والمتطلبات وفرص العمل.
        """
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        show(message["content"])

question = st.chat_input("Ask in English or Arabic...")

if question:
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        show(question)

    with st.chat_message("assistant"):
        with st.spinner("REX AI is thinking..."):
            try:
                response = bot.reply(
                    st.session_state.session,
                    question,
                )
                if not isinstance(response, str):
                    response = str(response)
            except Exception:
                response = (
                    "Sorry, something went wrong. Please try again."
                )

        show(response)

    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )
