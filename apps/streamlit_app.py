
"""REX AI — Smart Academy Assistant"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st
from rex.assistant.engine import RexAssistant, Session

st.set_page_config(
    page_title="REX AI | Smart Academy",
    page_icon="🎓",
    layout="centered"
)

st.markdown("""
<style>

.stApp {
    background-color: #f5f7fb;
    color: #1f2937;
}

.block-container {
    padding-top: 2rem;
    max-width: 850px;
}

h1, h2, h3, p, li, .stCaption {
    color: #1f2937 !important;
}

h1 {
    color: #173b67 !important;
}

.stChatMessage {
    border-radius: 12px;
    padding: 12px;
    color: #1f2937 !important;
}

.stChatMessage p,
.stChatMessage li {
    color: #1f2937 !important;
    unicode-bidi: plaintext;
    text-align: start;
}

[data-testid="stChatMessage"]:has(
    [data-testid="chatAvatarIcon-user"]
) {
    background-color: #e5eefb;
}

[data-testid="stChatMessage"]:has(
    [data-testid="chatAvatarIcon-assistant"]
) {
    background-color: #ffffff;
    border: 1px solid #e1e7ef;
}

[data-testid="stChatInput"] {
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)

st.title("🎓 REX AI")
st.subheader("Your Smart Academy Assistant")
st.caption("Course recommendations • English & العربية")

st.markdown("""
Welcome! 👋

I'm **REX**, your course assistant. I can help you explore
training courses and find options that match your interests.

**مرحباً!** يمكنني مساعدتك في استكشاف الدورات التدريبية
واختيار ما يناسب اهتماماتك.
""")

if "bot" not in st.session_state:
    st.session_state.bot = RexAssistant()
    st.session_state.s = Session()
    st.session_state.msgs = [
        ("assistant", st.session_state.bot.reply(
            st.session_state.s, "hello"
        ))
    ]

def show(role, text):
    st.chat_message(role).markdown(text.replace("\n", "  \n"))

for role, text in st.session_state.msgs:
    show(role, text)

if prompt := st.chat_input("Ask in English or Arabic…"):
    st.session_state.msgs.append(("user", prompt))
    answer = st.session_state.bot.reply(st.session_state.s, prompt)
    st.session_state.msgs.append(("assistant", answer))
    st.rerun()
