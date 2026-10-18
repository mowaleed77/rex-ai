
import streamlit as st
from rex.assistant.engine import RexAssistant, Session

st.set_page_config(
    page_title="REX AI | Smart Academy",
    page_icon="🎓",
    layout="centered"
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #f5f7fb;
        color: #1f2937;
    }

    h1, h2, h3 {
        color: #163b65 !important;
    }

    .stChatMessage {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 12px;
    }

    [data-testid="stChatInput"] textarea {
        color: #222222 !important;
        -webkit-text-fill-color: #222222 !important;
        background-color: #ffffff !important;
        caret-color: #222222 !important;
        opacity: 1 !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #666666 !important;
        -webkit-text-fill-color: #666666 !important;
        opacity: 1 !important;
    }

    [data-testid="stChatInputSubmitButton"] {
        color: #ffffff !important;
    }

    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessageContent"] p {
        color: #1f2937 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🎓 REX AI | Smart Academy")
st.caption("Your bilingual assistant for academy courses")

if "bot" not in st.session_state:
    st.session_state.bot = RexAssistant()

if "session" not in st.session_state:
    st.session_state.session = Session()

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.markdown(
        """
        ### Welcome to REX AI!

        Ask me about courses, prices, duration, prerequisites, and career opportunities.

        **مرحباً بك في REX AI!**

        اسألني عن الكورسات والأسعار والمدة والمتطلبات وفرص العمل.
        """
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask in English or Arabic...")

if question:
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("REX AI is thinking..."):
            try:
                response = st.session_state.bot.reply(
                    st.session_state.session,
                    question
                )
            except Exception as error:
                response = f"Sorry, something went wrong: {error}"

        if not isinstance(response, str):
            response = str(response)

        st.markdown(response)

    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )
