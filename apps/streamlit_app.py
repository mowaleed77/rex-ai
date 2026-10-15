"""Demo UI: streamlit run apps/streamlit_app.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from rex.assistant.engine import RexAssistant, Session

st.set_page_config(page_title="REX AI", page_icon="🎓")
# Per-paragraph text direction so Arabic replies align right-to-left and English left-to-right
st.markdown("<style>.stChatMessage p, .stChatMessage li {unicode-bidi: plaintext; text-align: start;}</style>", unsafe_allow_html=True)
st.title("🎓 REX Assistant")
st.caption("Course recommendation chatbot (Sprint 1 prototype) — Arabic & English")

if "bot" not in st.session_state:
    st.session_state.bot, st.session_state.s = RexAssistant(), Session()
    st.session_state.msgs = [("assistant", st.session_state.bot.reply(st.session_state.s, "hello"))]

def show(role, text):
    # keep the bot's line breaks (markdown ignores single newlines)
    st.chat_message(role).markdown(text.replace("\n", "  \n"))

for role, text in st.session_state.msgs:
    show(role, text)
if prompt := st.chat_input("Type in Arabic or English…"):
    st.session_state.msgs.append(("user", prompt))
    st.session_state.msgs.append(("assistant", st.session_state.bot.reply(st.session_state.s, prompt)))
    st.rerun()
