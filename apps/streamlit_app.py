
"""REX AI Smart Academy - Streamlit interface."""

import sys
import json
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st
from rex.assistant.engine import Session
from rex.assistant.rag import RagAssistant
from rex.agents.orchestrator import Orchestrator


st.set_page_config(
    page_title="REX AI | Smart Academy",
    page_icon="🎓",
    layout="wide",
)

st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #e5e7eb; }
h1, h2, h3 { color: #8ab4f8 !important; }
.stMarkdown, .stMarkdown p, .stMarkdown li { color: #e5e7eb; }
[data-testid="stSidebar"] { background-color: #141824; }
.stChatMessage {
    background-color: #1a1f2b;
    border: 1px solid #2d3748;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.title("🎓 REX AI | Smart Academy")
st.caption("Bilingual Academy Assistant and Multi-Agent System")

# Initialize components
if "bot" not in st.session_state:
    st.session_state.bot = RagAssistant()

if "session" not in st.session_state:
    st.session_state.session = Session()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

bot = st.session_state.bot
orchestrator = st.session_state.orchestrator

# Agent input examples. RFP uses local sample data by default.
default_tasks = {
    "curriculum": {
        "action": "generate",
        "course": "Python for Data Analysis",
        "level": "Beginner",
        "learning_outcomes": [
            "Write Python code",
            "Analyze datasets",
            "Create visualizations"
        ],
        "duration_hours": 12
    },
    "document": {
        "document_type": "course_description",
        "title": "Python for Data Analysis",
        "content": [
            "This course introduces Python programming.",
            "Students learn Pandas and data analysis.",
            "Students practice creating visualizations."
        ],
        "output_dir": "generated_docs/streamlit"
    },
    "marketing": {
        "course": {
            "title": "Python for Data Analysis",
            "description": "Learn Python, Pandas, and data visualization.",
            "duration_hours": 12,
            "price": "4500 EGP",
            "promotion": "15% early registration discount"
        },
        "target_audience": "Beginners",
        "channels": ["instagram", "linkedin"],
        "variations": 2
    },
    "rfp_research": {
        "today": "2026-10-26",
        "country": "Egypt",
        "topic": "training",
        "opportunities": [
            {
                "title": "Python Training Program",
                "country": "Egypt",
                "organization": "Sample Organization",
                "deadline": "2027-12-31",
                "description": "A technical training and education program.",
                "source_url": "https://example.com/sample-rfp"
            }
        ]
    }
}

chat_tab, agents_tab = st.tabs(["💬 REX Chatbot", "🤖 Agent Testing"])

# ---------------- CHATBOT ----------------
with chat_tab:
    st.subheader("Chat with REX AI")

    llm = bot.llm
    if bot.llm_enabled and llm is not None:
        st.success(f"LLM + RAG enabled — {llm.model}")
    else:
        st.warning("Rule-based mode: LLM is unavailable.")

    st.caption(f"{len(bot.retriever.chunks)} knowledge chunks loaded")
    st.caption("Ask questions in English or Arabic.")

    if not st.session_state.messages:
        st.info(
            "Welcome to REX AI! Ask about courses, prices, duration, "
            "prerequisites, and career opportunities.\n\n"
            "مرحباً بك في REX AI! اسأل عن الكورسات والأسعار والمتطلبات."
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
                    response = bot.reply(
                        st.session_state.session,
                        question,
                    )
                    if not isinstance(response, str):
                        response = str(response)
                except Exception as error:
                    response = f"Something went wrong: {error}"

            st.markdown(response)

        st.session_state.messages.append(
            {"role": "assistant", "content": response}
        )

# ---------------- AGENT TESTING ----------------
with agents_tab:
    st.subheader("Test the REX AI Agents")
    st.write("Choose an agent, edit its JSON input, and run it.")

    agent_names = [
        "curriculum",
        "document",
        "marketing",
        "rfp_research"
    ]

    selected_agent = st.selectbox(
        "Select an agent",
        agent_names,
        format_func=lambda name: {
            "curriculum": "📚 Curriculum Agent",
            "document": "📄 Document Agent",
            "marketing": "📢 Marketing Agent",
            "rfp_research": "🔎 RFP Research Agent"
        }[name]
    )

    st.caption(
        "The example input is editable. RFP testing uses sample data "
        "and does not perform a live search unless you remove the "
        "'opportunities' field."
    )

    task_text = st.text_area(
        "Agent input (JSON)",
        value=json.dumps(
            default_tasks[selected_agent],
            ensure_ascii=False,
            indent=2
        ),
        height=350,
        key=f"task_{selected_agent}"
    )

    if st.button("▶ Run Agent", type="primary"):
        try:
            task = json.loads(task_text)

            if not isinstance(task, dict):
                st.error("The JSON input must be an object.")
            else:
                with st.spinner(f"Running {selected_agent}..."):
                    result = orchestrator.dispatch(selected_agent, task)

                st.session_state["last_agent_name"] = selected_agent
                st.session_state["last_agent_ok"] = result.ok
                st.session_state["last_agent_message"] = result.message
                st.session_state["last_agent_output"] = result.output

        except json.JSONDecodeError as error:
            st.error(f"Invalid JSON: {error}")
        except Exception as error:
            st.error(f"Agent test failed: {error}")

    if "last_agent_name" in st.session_state:
        st.divider()
        st.subheader(
            f"Result: {st.session_state['last_agent_name']}"
        )

        if st.session_state["last_agent_ok"]:
            st.success(st.session_state["last_agent_message"])
        else:
            st.error(st.session_state["last_agent_message"])

        output = st.session_state["last_agent_output"]
        st.json(output if output is not None else {})

        if (
            st.session_state["last_agent_name"] == "document"
            and st.session_state["last_agent_ok"]
            and output
        ):
            pdf_path = pathlib.Path(output.get("file_path", ""))

            if pdf_path.is_file():
                with pdf_path.open("rb") as pdf_file:
                    st.download_button(
                        "Download generated PDF",
                        data=pdf_file.read(),
                        file_name=pdf_path.name,
                        mime="application/pdf"
                    )
