import json
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rex.assistant.engine import Session, RexAssistant
from rex.assistant.rag import RagAssistant
from rex.agents.orchestrator import Orchestrator
from rex.rag.llm import LLMClient
from rex.rag.retriever import Retriever


st.set_page_config(
    page_title="REX AI | Smart Academy",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# Professional styling
# --------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --rex-primary: #173f70;
        --rex-secondary: #2878b5;
        --rex-background: #f4f7fb;
        --rex-border: #dce5ef;
        --rex-text: #1d2939;
        --rex-muted: #667085;
    }

    .stApp {
        background: var(--rex-background);
        color: var(--rex-text);
    }

    [data-testid="stHeader"] {
        background: rgba(244, 247, 251, 0.96);
    }

    .block-container {
        max-width: 1450px;
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        color: var(--rex-primary) !important;
        letter-spacing: -0.3px;
    }

    p, label, li {
        color: var(--rex-text);
    }

    .rex-hero {
        background: linear-gradient(120deg, #173f70, #2878b5);
        color: #ffffff;
        padding: 26px 30px;
        border-radius: 18px;
        margin-bottom: 22px;
        box-shadow: 0 8px 24px rgba(23, 63, 112, 0.12);
    }

    .rex-hero h1 {
        color: #ffffff !important;
        font-size: 2rem;
        margin: 0 0 8px 0;
    }

    .rex-hero p {
        color: #e7f0fb !important;
        font-size: 1rem;
        margin: 0;
    }

    .rex-card {
        background: #ffffff;
        border: 1px solid var(--rex-border);
        border-radius: 14px;
        padding: 18px;
        min-height: 105px;
        box-shadow: 0 2px 8px rgba(16, 24, 40, 0.03);
    }

    .rex-card-label {
        color: var(--rex-muted);
        font-size: 0.84rem;
        margin-bottom: 7px;
    }

    .rex-card-value {
        color: var(--rex-primary);
        font-size: 1.3rem;
        font-weight: 700;
        overflow-wrap: anywhere;
    }

    .rex-card-note {
        color: var(--rex-muted);
        font-size: 0.8rem;
        margin-top: 5px;
    }

    [data-testid="stTabs"] [role="tablist"] {
        gap: 8px;
        border-bottom: 1px solid var(--rex-border);
    }

    [data-testid="stTabs"] button[role="tab"] {
        color: var(--rex-primary);
        font-weight: 650;
        padding: 12px 18px;
        border-radius: 10px 10px 0 0;
    }

    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: #e5eef9;
        border-bottom: 3px solid var(--rex-secondary);
    }

    /* Chat messages */

    [data-testid="stChatMessage"] {
        background: #ffffff;
        color: var(--rex-text);
        border: 1px solid var(--rex-border);
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 12px;
        min-width: 0;
    }

    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow-wrap: anywhere;
        color: var(--rex-text) !important;
    }

    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] span {
        color: var(--rex-text) !important;
        line-height: 1.65;
    }

    [data-testid="stChatMessage"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 12px 0 !important;
        background: #ffffff !important;
        color: var(--rex-text) !important;
        font-size: 0.9rem !important;
    }

    [data-testid="stChatMessage"] th,
    [data-testid="stChatMessage"] td {
        padding: 10px 12px !important;
        border: 1px solid var(--rex-border) !important;
        color: var(--rex-text) !important;
        text-align: left !important;
        vertical-align: top !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
    }

    [data-testid="stChatMessage"] th {
        background: #e5eef9 !important;
        color: var(--rex-primary) !important;
        font-weight: 700 !important;
    }

    [data-testid="stChatMessage"] tr:nth-child(even) td {
        background: #f7f9fc !important;
    }

    [data-testid="stChatMessage"] pre {
        max-width: 100%;
        overflow-x: auto;
        border-radius: 8px;
    }

    [data-testid="stChatMessage"] code {
        color: var(--rex-primary);
    }

    /* Inputs */

    [data-testid="stChatInput"] textarea,
    [data-testid="stTextArea"] textarea,
    [data-testid="stTextInput"] input {
        color: #1d2939 !important;
        -webkit-text-fill-color: #1d2939 !important;
        background-color: #ffffff !important;
        caret-color: #1d2939 !important;
        border-radius: 10px;
    }

    [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stTextArea"] textarea::placeholder {
        color: #667085 !important;
        -webkit-text-fill-color: #667085 !important;
    }

    /* Buttons */

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 9px;
        font-weight: 600;
        min-height: 42px;
        transition: 0.15s ease;
    }

    .stButton > button[kind="primary"] {
        background: var(--rex-primary);
        border: 1px solid var(--rex-primary);
        color: #ffffff;
    }

    .stButton > button[kind="primary"]:hover {
        background: var(--rex-secondary);
        border-color: var(--rex-secondary);
        color: #ffffff;
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--rex-border);
    }

    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: var(--rex-primary) !important;
    }

    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    hr {
        border-color: var(--rex-border);
    }

    .rex-footer {
        color: var(--rex-muted);
        font-size: 0.82rem;
        text-align: center;
        padding-top: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# Session state and initialization
# --------------------------------------------------

def initialize_state():
    defaults = {
        "bot": None,
        "session": None,
        "messages": [],
        "orchestrator": None,
        "llm_api_tested": False,
        "llm_api_ok": False,
        "llm_api_error": "",
        "last_api_test_model": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state.bot is None:
        st.session_state.bot = RagAssistant(
            fallback=RexAssistant(),
            use_env_llm=True,
        )

    if st.session_state.session is None:
        st.session_state.session = Session()

    if st.session_state.orchestrator is None:
        st.session_state.orchestrator = Orchestrator()


# --------------------------------------------------
# System status
# --------------------------------------------------

@st.cache_resource
def load_retriever():
    return Retriever()


def get_system_status():
    try:
        retriever = load_retriever()
        document_count = len(retriever.chunks)
        rag_error = None
    except Exception as error:
        retriever = None
        document_count = 0
        rag_error = f"{type(error).__name__}: {error}"

    try:
        llm = LLMClient.from_env()
        llm_configured = llm is not None

        if llm is not None:
            model_name = llm.model
            base_url = llm.base_url
        else:
            model_name = "Not configured"
            base_url = ""

        llm_error = None

    except Exception as error:
        llm = None
        llm_configured = False
        model_name = "Configuration error"
        base_url = ""
        llm_error = f"{type(error).__name__}: {error}"

    return {
        "retriever": retriever,
        "document_count": document_count,
        "rag_error": rag_error,
        "llm": llm,
        "llm_configured": llm_configured,
        "model_name": model_name,
        "base_url": base_url,
        "llm_error": llm_error,
        "llm_api_tested": st.session_state.llm_api_tested,
        "llm_api_ok": st.session_state.llm_api_ok,
    }


def render_status_card(label, value, note=""):
    st.markdown(
        f"""
        <div class="rex-card">
            <div class="rex-card-label">{label}</div>
            <div class="rex-card-value">{value}</div>
            <div class="rex-card-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(status):
    with st.sidebar:
        st.markdown("## 🎓 REX AI")
        st.caption("Smart Academy · System dashboard")
        st.divider()

        st.markdown("### System status")

        if status["llm_configured"]:
            st.success("LLM client configured")
        else:
            st.warning("LLM client not configured")

        if status["llm_api_tested"]:
            if status["llm_api_ok"]:
                st.success("Live API test passed")
            else:
                st.error("Live API test failed")
        else:
            st.info("Live API not tested this session")

        if status["rag_error"]:
            st.error("RAG retriever could not load")
        elif status["document_count"] > 0:
            st.success(
                f"RAG documents loaded: {status['document_count']}"
            )
        else:
            st.warning("No RAG documents found")

        st.caption(f"Model: {status['model_name']}")

        if status["base_url"]:
            st.caption(f"Endpoint: {status['base_url']}")

        st.divider()

        if st.button(
            "Test LLM connection",
            use_container_width=True,
            key="test_llm_connection",
        ):
            if not status["llm_configured"]:
                st.session_state.llm_api_tested = True
                st.session_state.llm_api_ok = False
                st.session_state.llm_api_error = (
                    "No API key was found in the environment or .env file."
                )
                st.session_state.last_api_test_model = ""
            else:
                with st.spinner("Testing the configured LLM API..."):
                    try:
                        test_response = status["llm"](
                            [
                                {
                                    "role": "user",
                                    "content": (
                                        "Reply with exactly: "
                                        "REX_CONNECTION_OK"
                                    ),
                                }
                            ]
                        )

                        if (
                            isinstance(test_response, str)
                            and "REX_CONNECTION_OK" in test_response
                        ):
                            st.session_state.llm_api_ok = True
                            st.session_state.llm_api_error = ""
                        else:
                            st.session_state.llm_api_ok = False
                            st.session_state.llm_api_error = (
                                "The API responded, but the response "
                                "did not match the expected test text."
                            )

                    except Exception as error:
                        st.session_state.llm_api_ok = False
                        st.session_state.llm_api_error = (
                            f"Request failed ({type(error).__name__}). "
                            "Check the terminal for detailed diagnostics."
                        )

                    st.session_state.llm_api_tested = True
                    st.session_state.last_api_test_model = (
                        status["model_name"]
                    )

            st.rerun()

        if status["llm_api_tested"]:
            if status["llm_api_ok"]:
                st.caption(
                    "The most recent API test succeeded using "
                    f"{st.session_state.last_api_test_model}."
                )
            else:
                st.caption(st.session_state.llm_api_error)

        st.divider()

        if st.button(
            "Clear chatbot history",
            use_container_width=True,
            key="clear_chat_history",
        ):
            st.session_state.messages = []
            st.session_state.session = Session()
            st.rerun()

        st.caption("REX AI · Sprint prototype")


# --------------------------------------------------
# Default agent tasks
# --------------------------------------------------

def get_default_tasks():
    return {
        "curriculum": {
            "action": "generate",
            "course": "Python for Data Analysis",
            "level": "Beginner",
            "learning_outcomes": [
                "Write Python code",
                "Analyze datasets",
                "Create visualizations",
            ],
            "duration_hours": 12,
        },
        "document": {
            "document_type": "curriculum_report",
            "title": "Python Course Report",
            "content": [
                "Level: Beginner",
                "Duration: 12 hours",
                "Module 1: Python Fundamentals",
                "Module 2: Data Analysis",
            ],
        },
        "marketing": {
            "course": {
                "title": "Python for Data Analysis",
                "description": (
                    "Learn Python for data analysis and visualization."
                ),
                "duration_hours": 40,
                "price": 4500,
                "promotion": "15% early registration",
            },
            "target_audience": "University students",
            "channels": ["instagram", "linkedin"],
            "variations": 2,
        },
        "rfp_research": {
            "country": "Egypt",
            "topic": "AI training",
            "today": "2026-10-26",
            "opportunities": [
                {
                    "title": "Example AI Training Opportunity",
                    "organization": "Example Organization",
                    "country": "Egypt",
                    "deadline": "2027-12-31",
                    "source_url": "https://example.com/training-opportunity",
                    "description": (
                        "An education and technology training opportunity."
                    ),
                    "category": "Training",
                }
            ],
        },
    }


# --------------------------------------------------
# Chatbot interface
# --------------------------------------------------

def render_chatbot(status):
    st.subheader("💬 REX Chatbot")

    st.caption(
        "Ask about academy courses, prices, durations, admission, "
        "and career opportunities in English or Arabic."
    )

    with st.expander("About this assistant"):
        st.write(
            "REX combines academy knowledge, retrieval from its "
            "knowledge documents, and configured language-model "
            "capabilities. The exact path depends on the question "
            "and the assistant's routing logic."
        )

    if not st.session_state.messages:
        st.markdown(
            """
            <div style="
                background: white;
                border: 1px solid #dce5ef;
                border-radius: 14px;
                padding: 22px;
                margin: 12px 0 20px 0;
            ">
                <h3 style="margin-top:0;">Welcome to REX AI 👋</h3>
                <p>How can I help you with your learning journey today?</p>
                <p style="color:#667085;">
                    Explore courses, compare prices, or ask about prerequisites.
                    You can chat in English or Arabic.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        example_columns = st.columns(3)

        with example_columns[0]:
            st.markdown("**📚 Courses**")
            st.caption("What courses are available?")

        with example_columns[1]:
            st.markdown("**💰 Pricing**")
            st.caption("How much does a course cost?")

        with example_columns[2]:
            st.markdown("**🌐 Arabic**")
            st.caption("ما هي الدورات المتاحة؟")

    # Display saved conversation in chronological order.
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(
                message["content"],
                unsafe_allow_html=False,
            )

    # Keep Streamlit's native chat input.
    question = st.chat_input(
        "Message REX AI in English or Arabic...",
        key="rex_chat_input",
    )

    if question is None or not question.strip():
        return

    question = question.strip()

    # Save and display the user's message immediately.
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        st.markdown(question, unsafe_allow_html=False)

    # Generate the assistant response.
    with st.chat_message("assistant"):
        with st.spinner("REX is thinking..."):
            try:
                response = st.session_state.bot.reply(
                    st.session_state.session,
                    question,
                )

                if not isinstance(response, str):
                    response = str(response)

                if not response.strip():
                    response = (
                        "I couldn't generate a useful answer. "
                        "Please try rephrasing your question."
                    )

            except Exception:
                response = (
                    "I'm sorry, but REX couldn't process that message. "
                    "Please try again. If the problem continues, "
                    "check the application terminal."
                )

            st.markdown(
                response,
                unsafe_allow_html=False,
            )

    # Save the answer so it remains visible after the next rerun.
    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )


# --------------------------------------------------
# Agent results and downloads
# --------------------------------------------------

def render_agent_result(result, selected_agent):
    output = result.output if isinstance(result.output, dict) else {}

    if result.ok:
        st.success(f"{selected_agent} completed successfully.")
    else:
        st.error(result.message or "The agent reported a failure.")

    result_data = {
        "agent": result.agent,
        "ok": result.ok,
        "message": result.message,
        "output": output,
        "sources": result.sources,
    }

    output_text = json.dumps(
        result_data,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    st.markdown("### Execution result")
    st.json(result_data)

    st.download_button(
        label="Download result JSON",
        data=output_text.encode("utf-8"),
        file_name=f"{selected_agent}_result.json",
        mime="application/json",
        key=f"download_json_{selected_agent}",
        use_container_width=True,
    )

    if not result.ok:
        return

    pdf_path = output.get("file_path") or output.get("pdf_path")

    if not pdf_path:
        st.info(
            "This agent did not return a PDF file path. "
            "The JSON result is still available for download."
        )
        return

    try:
        pdf_file_path = Path(pdf_path).expanduser()

        if not pdf_file_path.is_absolute():
            pdf_file_path = PROJECT_ROOT / pdf_file_path

        pdf_file_path = pdf_file_path.resolve()

        if not pdf_file_path.is_file():
            st.warning(
                "The agent returned a PDF path, but the file "
                "could not be found."
            )
            return

        if pdf_file_path.suffix.lower() != ".pdf":
            st.warning(
                "The generated document path does not point to a PDF."
            )
            return

        st.download_button(
            label="Download generated PDF",
            data=pdf_file_path.read_bytes(),
            file_name=pdf_file_path.name,
            mime="application/pdf",
            key=f"download_pdf_{selected_agent}",
            use_container_width=True,
        )

    except OSError:
        st.warning(
            "The generated PDF could not be read. "
            "Check the file path and permissions."
        )


# --------------------------------------------------
# Agent testing interface
# --------------------------------------------------

def render_agent_testing():
    st.subheader("🤖 Agent Testing")

    st.caption(
        "Run an individual agent, edit its JSON input, and inspect "
        "or download the result."
    )

    agent_labels = {
        "Curriculum Agent": "curriculum",
        "Document Agent": "document",
        "Marketing Agent": "marketing",
        "RFP Research Agent": "rfp_research",
    }

    orchestrator = st.session_state.orchestrator
    available_agents = orchestrator.agents

    selected_label = st.selectbox(
        "Select an agent",
        list(agent_labels.keys()),
        key="selected_agent_label",
    )

    selected_agent = agent_labels[selected_label]

    if selected_agent not in available_agents:
        st.error(
            f"{selected_label} is not registered in the orchestrator. "
            "Check the agent name and its registration."
        )

        st.markdown("### Registered agents")

        for label, agent_name in agent_labels.items():
            if agent_name in available_agents:
                st.success(f"{label}: registered")
            else:
                st.error(f"{label}: not registered")

        return

    default_tasks = get_default_tasks()
    task_key = f"task_json_{selected_agent}"

    if task_key not in st.session_state:
        st.session_state[task_key] = json.dumps(
            default_tasks[selected_agent],
            indent=2,
            ensure_ascii=False,
        )

    with st.expander("About agent testing", expanded=False):
        st.write(
            "The default tasks are examples for testing the interface. "
            "Review the task JSON before running an agent, and confirm "
            "that its output meets your project's requirements."
        )

    task_text = st.text_area(
        "Task JSON",
        height=320,
        key=task_key,
        help=(
            "Enter a valid JSON object. The selected agent determines "
            "which fields are required."
        ),
    )

    run_clicked = st.button(
        "▶ Run Agent",
        type="primary",
        key="run_selected_agent",
        use_container_width=True,
    )

    if run_clicked:
        try:
            task = json.loads(task_text)
        except json.JSONDecodeError as error:
            st.error(
                f"Invalid JSON at line {error.lineno}, "
                f"column {error.colno}: {error.msg}"
            )
            return

        if not isinstance(task, dict):
            st.error(
                "The task must be a JSON object enclosed in curly braces."
            )
            return

        with st.spinner(f"Running {selected_label}..."):
            try:
                result = orchestrator.dispatch(selected_agent, task)
                render_agent_result(result, selected_agent)
            except Exception:
                st.error(
                    f"{selected_label} could not complete the request. "
                    "Check the application terminal for the detailed error."
                )

    st.divider()
    st.markdown("### Agent registry")

    columns = st.columns(2)

    for index, (label, agent_name) in enumerate(agent_labels.items()):
        with columns[index % 2]:
            if agent_name in available_agents:
                st.success(f"**{label}**")
                st.caption(f"Registered as `{agent_name}`")
            else:
                st.error(f"**{label}**")
                st.caption(f"`{agent_name}` is not registered")


# --------------------------------------------------
# Application entry point
# --------------------------------------------------

initialize_state()

system_status = get_system_status()

render_sidebar(system_status)

st.markdown(
    """
    <div class="rex-hero">
        <h1>REX AI | Smart Academy</h1>
        <p>
            Your bilingual academy assistant and multi-agent workspace.
            Ask questions, test agents, and inspect generated results.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

status_columns = st.columns(3)

with status_columns[0]:
    render_status_card(
        "Language model",
        "Configured" if system_status["llm_configured"] else "Not configured",
        system_status["model_name"],
    )

with status_columns[1]:
    if system_status["rag_error"]:
        rag_value = "Unavailable"
        rag_note = "Retriever initialization failed"
    else:
        rag_value = str(system_status["document_count"])
        rag_note = "Knowledge documents loaded"

    render_status_card("RAG knowledge base", rag_value, rag_note)

with status_columns[2]:
    if not system_status["llm_api_tested"]:
        api_value = "Not tested"
        api_note = "Use the sidebar to test the API"
    elif system_status["llm_api_ok"]:
        api_value = "Connected"
        api_note = "Most recent API test succeeded"
    else:
        api_value = "Test failed"
        api_note = "Check the sidebar for details"

    render_status_card("Live API check", api_value, api_note)

if system_status["rag_error"]:
    st.warning(
        "The RAG retriever could not be initialized. "
        "Check that the knowledge documents exist and are readable."
    )
elif system_status["document_count"] == 0:
    st.warning(
        "No Markdown knowledge documents were loaded. "
        "Check the data/rag_docs directory."
    )

tab_chat, tab_agents = st.tabs(
    ["💬 REX Chatbot", "🤖 Agent Testing"]
)

with tab_chat:
    render_chatbot(system_status)

with tab_agents:
    render_agent_testing()

st.markdown(
    """
    <div class="rex-footer">
        REX AI Smart Academy · Bilingual assistant · Multi-agent prototype
    </div>
    """,
    unsafe_allow_html=True,
)
