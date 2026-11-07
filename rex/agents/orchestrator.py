"""REX AI Orchestrator: the one agent that talks to all the others and carries out what is asked.

Two ways to use it:

1. `dispatch(agent_name, task)`          - run one agent directly (unchanged, used by tests / UI tabs).
2. `handle("make a curriculum and a campaign for Excel for Business Analysis", context)`
                                           - understand a plain-language request (English or Arabic),
                                             plan the steps, call the right agents in order, pass the
                                             output of one agent to the next, and report back.

Workflows (also callable by name with `run_workflow`):
    course_launch  curriculum -> [human approval] -> PDFs -> marketing campaign -> [admin review]
    curriculum     curriculum draft (+ PDF)
    documents      PDFs from the current curriculum
    campaign       marketing campaign for a course
    rfp            RFP research (+ e-mail digest on request)

Humans stay in control: the orchestrator never approves a curriculum or a campaign on its own.
It stops with `awaiting` set to "curriculum_approval" or "campaign_review" until a reviewer acts.
Uses a LangGraph workflow for single dispatches when `langgraph` is installed, and plain calls otherwise.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypedDict

from rex.utils import catalog as cat
from rex.utils.arabic import is_mostly_arabic

from .base import Agent, AgentResult
from .curriculum import CurriculumAgent
from .document import DocumentAgent
from .marketing import MarketingAgent
from .rfp import RfpAgent
from .rfp_email import RfpEmailAgent

try:  # optional dependency
    from langgraph.graph import StateGraph, END
except ImportError:  # pragma: no cover - depends on the environment
    StateGraph = None
    END = None

ROOT = Path(__file__).resolve().parents[2]


class WorkflowState(TypedDict, total=False):
    agent_name: str
    task: dict[str, Any]
    result: AgentResult


@dataclass
class OrchestratorResult:
    ok: bool
    intent: str
    message: str
    steps: list[dict] = field(default_factory=list)       # what was done, in order
    artifacts: dict = field(default_factory=dict)          # curriculum, pdfs, campaign, rfp, email ...
    awaiting: str | None = None                            # curriculum_approval | campaign_review
    needs_input: list[str] = field(default_factory=list)   # facts the user still has to give
    context: dict = field(default_factory=dict)            # pass back in on the next call (follow-ups)
    reply: str = ""                                        # set for plain chat answers
    agent: str = "orchestrator"                            # kept for the original AgentResult-style contract
    output: dict = field(default_factory=dict)             # original format: {"stages": {...}, "document": ..., ...}


# --------------------------------------------------------------- intent rules
_CHANNEL_WORDS = {
    "instagram": "instagram", "انستجرام": "instagram", "إنستجرام": "instagram", "انستغرام": "instagram",
    "facebook": "facebook", "فيسبوك": "facebook", "فيس بوك": "facebook",
    "linkedin": "linkedin", "لينكدإن": "linkedin", "لينكد إن": "linkedin", "لينكدان": "linkedin",
    "email": "email", "e-mail": "email", "newsletter": "email", "ايميل": "email", "إيميل": "email",
    "whatsapp": "whatsapp", "واتساب": "whatsapp", "واتس اب": "whatsapp",
}
_LEVELS = {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced",
           "مبتدئ": "Beginner", "مبتدئين": "Beginner", "متوسط": "Intermediate", "متقدم": "Advanced"}
_RE_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
_RE_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h\b|ساعة|ساعات)", re.I)


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def detect_intent(text: str) -> str:
    low = text.casefold()
    rfp = _has(low, ("rfp", "tender", "tenders", "rfq", "مناقصة", "مناقصات", "عطاء", "عطاءات"))
    campaign = _has(low, ("campaign", "marketing", "social media", "caption", "ad copy", "post for", "promote",
                          "حملة", "حملات", "تسويق", "إعلان", "اعلان", "منشور", "ترويج"))
    curriculum = _has(low, ("curriculum", "syllabus", "course outline", "منهج", "مناهج", "خطة دراسية", "محتوى الدورة"))
    document = _has(low, ("pdf", "document", "course description", "report", "مستند", "ملف", "وصف الدورة", "تقرير"))
    launch = _has(low, ("launch", "end to end", "end-to-end", "full workflow", "new course", "اطلاق", "إطلاق",
                        "اطلق", "أطلق", "دورة جديدة", "كورس جديد"))
    if rfp:
        return "rfp"
    if launch or (curriculum and campaign):
        return "course_launch"
    if campaign:
        return "campaign"
    if document:
        return "documents"
    if curriculum:
        return "curriculum"
    if _has(low, ("help", "what can you do", "مساعدة", "ماذا تستطيع", "ايه اللي تقدر")):
        return "help"
    return "chat"


class Orchestrator:
    def __init__(self, docs_dir: Path | str | None = None, courses: list[dict] | None = None,
                 assistant=None, on_event: Callable[[dict], None] | None = None):
        agents = (RfpAgent(), CurriculumAgent(), DocumentAgent(), MarketingAgent(), RfpEmailAgent())
        self.agents: dict[str, Agent] = {agent.name: agent for agent in agents}
        self.docs_dir = Path(docs_dir) if docs_dir else ROOT / "generated_docs"
        self.courses = courses if courses is not None else cat.load_courses()
        self.assistant = assistant            # optional chatbot used for course questions
        self.on_event = on_event              # hook: the UI stores events in the activity log
        self.trace: list[dict] = []

        self.workflow = None
        if StateGraph is not None:
            graph = StateGraph(WorkflowState)
            graph.add_node("dispatch", self._dispatch_node)
            graph.set_entry_point("dispatch")
            graph.add_edge("dispatch", END)
            self.workflow = graph.compile()

    # ---------------------------------------------------------------- basics
    def register(self, agent: Agent):
        self.agents[agent.name] = agent

    def _log(self, agent: str, action: str, ok: bool, message: str) -> None:
        event = {"at": time.strftime("%H:%M:%S"), "agent": agent, "action": action, "ok": ok,
                 "message": message[:300]}
        self.trace.append(event)
        del self.trace[:-200]
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                pass

    def _run_agent(self, agent_name: str, task: dict) -> AgentResult:
        agent = self.agents.get(agent_name)
        if not agent:
            return AgentResult(agent_name, False, message=f"Unknown agent '{agent_name}'")
        try:
            result = agent.run(task)
        except Exception as error:
            result = AgentResult(agent_name, False, message=f"Agent error: {error}")
        self._log(agent_name, str(task.get("action") or task.get("document_type") or "run"),
                  result.ok, result.message)
        return result

    def _dispatch_node(self, state: WorkflowState) -> WorkflowState:
        return {"result": self._run_agent(state["agent_name"], state["task"])}

    def dispatch(self, agent_name: str, task: dict) -> AgentResult:
        if self.workflow is None:
            return self._run_agent(agent_name, task)
        state = self.workflow.invoke({"agent_name": agent_name, "task": task})
        return state["result"]

    # ------------------------------------------------------ natural language
    def parse_request(self, text: str, context: dict | None = None) -> dict:
        """Pull the facts out of a request: intent, course, language, level, hours, channels, e-mails."""
        context = context or {}
        low = text.casefold()
        course = cat.find_course_in_text(text, self.courses)
        custom = None
        if not course:
            m = re.search(r"(?:for|on|about|لدورة|عن|في)\s+(?:the\s+)?[\"'“]?([^\"'”,.;\n]{3,60}?)[\"'”]?"
                          r"(?:\s+(?:course|in|with|at|to|for|and|وحملة|و)\b|[,.;\n]|$)", text, re.I)
            custom = m.group(1).strip() if m else None
        language = "ar" if (is_mostly_arabic(text) or _has(low, ("in arabic", "arabic version", "بالعربي", "بالعربية"))) \
            else ("en" if "in english" in low else None)
        hours = _RE_HOURS.search(text)
        return {
            "intent": detect_intent(text),
            "course": course,
            "custom_title": custom,
            "language": language,
            "level": next((v for k, v in _LEVELS.items() if k in low), None),
            "hours": float(hours.group(1)) if hours else None,
            "channels": list(dict.fromkeys(v for k, v in _CHANNEL_WORDS.items() if k in low)) or None,
            "emails": _RE_EMAIL.findall(text),
            "country": "Egypt" if _has(low, ("egypt", "مصر")) else ("Saudi Arabia" if _has(low, ("saudi", "ksa", "السعودية")) else None),
            "send": bool(re.search(r"\b(send|email it|e-mail it)\b|ارسل|أرسل", low)),
            "discover": not _has(low, ("don't search", "without searching")),
        }

    def handle(self, text: str, context: dict | None = None, **options) -> OrchestratorResult:
        """Understand `text`, run the needed agents, and return what happened.

        options (all optional): approved_by (reviewer who approves the curriculum), use_llm, language,
        recipients, send_email, opportunities (RFP items to process), variations.
        """
        context = dict(context or {})
        text = (text or "").strip()
        if not text:
            return OrchestratorResult(False, "help", "Tell me what you need, e.g. 'launch the Excel for "
                                      "Business Analysis course' or 'find training tenders in Egypt'.", context=context)
        req = self.parse_request(text, context)
        intent = req["intent"]
        if intent == "help":
            return OrchestratorResult(True, intent, self.help_text(req["language"] == "ar"), context=context)
        if intent == "chat":
            return self._chat(text, context)
        params = {**req, **{k: v for k, v in options.items() if v is not None}}
        return self.run_workflow(intent, params, context)

    @staticmethod
    def help_text(arabic: bool = False) -> str:
        if arabic:
            return ("أستطيع تنفيذ: إطلاق دورة كاملة (منهج ← مستندات PDF ← حملة تسويقية)، إنشاء منهج، إنشاء مستندات PDF، "
                    "إنشاء حملة تسويقية، والبحث عن مناقصات في مصر والسعودية مع إرسال ملخص بالبريد.")
        return ("I can: launch a course end to end (curriculum -> PDFs -> marketing campaign), create a curriculum, "
                "generate PDF documents, create a marketing campaign, and research tenders in Egypt and Saudi "
                "Arabia (with an e-mail digest). Name a course from the catalog or give a new title.")

    def _chat(self, text: str, context: dict) -> OrchestratorResult:
        if self.assistant is None:
            return OrchestratorResult(False, "chat", self.help_text(is_mostly_arabic(text)), context=context)
        from rex.assistant.engine import Session
        session = context.get("chat_session") or Session()
        context["chat_session"] = session
        try:
            reply = self.assistant.reply(session, text)
        except Exception as error:
            return OrchestratorResult(False, "chat", f"The assistant failed: {error}", context=context)
        self._log("assistant", "reply", True, "answered a course question")
        return OrchestratorResult(True, "chat", reply, reply=reply, context=context,
                                  steps=[{"step": "Answer the question", "agent": "assistant", "ok": True,
                                          "message": "answered from the knowledge base"}])

    # ------------------------------------------------------------- workflows
    def run_workflow(self, name: str, params: dict, context: dict | None = None) -> OrchestratorResult:
        context = dict(context or {})
        runner = {"course_launch": self._wf_launch, "curriculum": self._wf_curriculum,
                  "documents": self._wf_documents, "campaign": self._wf_campaign, "rfp": self._wf_rfp}.get(name)
        if runner is None:
            return OrchestratorResult(False, name, f"Unknown workflow '{name}'.", context=context)
        run = _Run(self, name, params, context)
        if name == "course_launch" and "intent" not in params and "learning_outcomes" in params:
            return self._course_launch_stages(run)  # original call style: explicit course data, no approval gate
        try:
            return runner(run)
        except _Stop as stop:
            return stop.result

    # ---- shared step helpers
    def _course_inputs(self, run: "_Run") -> dict:
        """Resolve course title, level, hours and outcomes from the catalog or the request."""
        p, ctx = run.params, run.context
        entry = p.get("course") if isinstance(p.get("course"), dict) else None
        if isinstance(p.get("course"), str):
            entry = cat.find_course(p["course"], self.courses)
        language = p.get("language") or ("ar" if entry is None and is_mostly_arabic(str(p.get("custom_title") or ""))
                                         else "en")
        if entry:
            ar = language == "ar"
            return {"entry": entry, "language": language,
                    "title": entry["title_ar"] if ar else entry["title_en"],
                    "level": p.get("level") or entry.get("level", "Beginner"),
                    "hours": p.get("hours") or entry.get("duration_hours", 24),
                    "outcomes": (entry.get("learning_outcomes_ar") if ar else None) or entry.get("learning_outcomes", [])}
        title = p.get("custom_title") or p.get("title") or (ctx.get("curriculum") or {}).get("course")
        if not title:
            raise _Stop(run.finish(False, "I could not tell which course you mean. Name a catalog course or give "
                                   "a title, for example: launch the course 'Excel for Business Analysis'.",
                                   needs_input=["course"]))
        outcomes = p.get("learning_outcomes") or (ctx.get("curriculum") or {}).get("learning_outcomes")
        return {"entry": None, "language": language, "title": title, "level": p.get("level") or "Beginner",
                "hours": p.get("hours") or 24, "outcomes": outcomes or []}

    def _ensure_curriculum(self, run: "_Run") -> dict:
        ctx = run.context
        info = self._course_inputs(run)
        existing = ctx.get("curriculum")
        if existing and not run.params.get("regenerate") and \
                existing.get("course", "").casefold() == info["title"].casefold():
            run.info = info
            return existing
        if not info["outcomes"]:
            raise _Stop(run.finish(False, f"'{info['title']}' is not in the catalog, so I need its learning outcomes "
                                   "(one per line) before I can design the curriculum.",
                                   needs_input=["learning_outcomes"]))
        res = run.step("Design the curriculum", "curriculum", {
            "action": "generate", "course": info["title"], "level": info["level"],
            "duration_hours": info["hours"], "learning_outcomes": info["outcomes"],
            "language": info["language"], "use_llm": bool(run.params.get("use_llm"))})
        if not res.ok:
            raise _Stop(run.finish(False, res.message))
        ctx["curriculum"] = res.output
        ctx["course_info"] = info["entry"]
        run.info = info
        return res.output

    def _approve_if_asked(self, run: "_Run", curriculum: dict) -> dict:
        reviewer = run.params.get("approved_by")
        if reviewer and curriculum.get("status_code") != "approved":
            res = run.step("Approve the curriculum", "curriculum",
                           {"action": "approve", "curriculum": curriculum, "reviewer": reviewer,
                            "note": run.params.get("approval_note", "")})
            if not res.ok:
                raise _Stop(run.finish(False, res.message))
            run.context["curriculum"] = res.output
            return res.output
        return curriculum

    def _make_pdfs(self, run: "_Run", curriculum: dict, types: tuple[str, ...]) -> dict:
        pdfs = {}
        for doc_type in types:
            res = run.step(f"Create PDF: {doc_type.replace('_', ' ')}", "document", {
                "document_type": doc_type, "curriculum": curriculum, "course_info": run.context.get("course_info"),
                "language": curriculum.get("language", "en"), "output_dir": str(self.docs_dir)})
            if res.ok:
                pdfs[doc_type] = res.output["file_path"]
        run.context["pdfs"] = pdfs
        return pdfs

    def _wf_curriculum(self, run: "_Run") -> OrchestratorResult:
        curriculum = self._approve_if_asked(run, self._ensure_curriculum(run))
        pdfs = self._make_pdfs(run, curriculum, ("curriculum_report",))
        awaiting = None if curriculum.get("status_code") == "approved" else "curriculum_approval"
        msg = f"Curriculum for {curriculum['course']} is ready ({curriculum['duration_hours']:g} hours, " \
              f"{len(curriculum['modules'])} modules)."
        if awaiting:
            msg += " It is a draft: a reviewer must revise or approve it before it is used elsewhere."
        return run.finish(True, msg, artifacts={"curriculum": curriculum, "pdfs": pdfs}, awaiting=awaiting)

    def _wf_documents(self, run: "_Run") -> OrchestratorResult:
        curriculum = self._approve_if_asked(run, self._ensure_curriculum(run))
        types = ("curriculum_report", "course_description")
        pdfs = self._make_pdfs(run, curriculum, types)
        awaiting = None if curriculum.get("status_code") == "approved" else "curriculum_approval"
        msg = f"Created {len(pdfs)} PDF document(s) for {curriculum['course']}."
        if awaiting:
            msg += " They are marked DRAFT until the curriculum is approved."
        return run.finish(bool(pdfs), msg, artifacts={"curriculum": curriculum, "pdfs": pdfs}, awaiting=awaiting)

    def _marketing_task(self, run: "_Run", curriculum: dict | None) -> dict:
        info = getattr(run, "info", None) or self._course_inputs(run)
        entry = info.get("entry") or run.context.get("course_info")
        course = cat.marketing_view(entry) if entry else {"title": info["title"]}
        p = run.params
        task = {"course": course, "curriculum": curriculum, "language": info["language"],
                "channels": p.get("channels") or ["instagram", "facebook", "linkedin", "email", "whatsapp"],
                "variations": p.get("variations", 2), "use_llm": bool(p.get("use_llm")),
                "objective": p.get("objective", "leads")}
        return task

    def _wf_campaign(self, run: "_Run") -> OrchestratorResult:
        curriculum = run.context.get("curriculum")
        info = self._course_inputs(run)
        run.info = info
        # use the curriculum from this conversation only when it is for the same course
        if curriculum and curriculum.get("course", "").casefold() != info["title"].casefold():
            curriculum = None
        res = run.step("Write the campaign", "marketing", self._marketing_task(run, curriculum))
        if not res.ok:
            return run.finish(False, res.message)
        run.context["campaign"] = res.output
        n = sum(len(v) for v in res.output["content"].values())
        return run.finish(True, f"Created {n} pieces of campaign content for {res.output['course_title']}. "
                          "An admin must review and approve it before anything is published.",
                          artifacts={"campaign": res.output}, awaiting="campaign_review")

    def _wf_launch(self, run: "_Run") -> OrchestratorResult:
        curriculum = self._ensure_curriculum(run)
        curriculum = self._approve_if_asked(run, curriculum)
        pdfs = self._make_pdfs(run, curriculum, ("curriculum_report", "course_description"))
        if curriculum.get("status_code") != "approved":
            return run.finish(
                True, f"Step 1 done: draft curriculum and draft PDFs for {curriculum['course']} are ready. "
                      "Approve (or revise) the curriculum and I will continue with the final PDFs and the "
                      "marketing campaign.",
                artifacts={"curriculum": curriculum, "pdfs": pdfs}, awaiting="curriculum_approval")
        res = run.step("Write the campaign from the approved curriculum", "marketing",
                       self._marketing_task(run, curriculum))
        if not res.ok:
            return run.finish(False, res.message, artifacts={"curriculum": curriculum, "pdfs": pdfs})
        run.context["campaign"] = res.output
        return run.finish(
            True, f"{curriculum['course']} is ready to launch: approved curriculum, {len(pdfs)} PDFs and a "
                  "multi-channel campaign. The campaign now waits for an admin review before publishing.",
            artifacts={"curriculum": curriculum, "pdfs": pdfs, "campaign": res.output}, awaiting="campaign_review")

    def _course_launch_stages(self, run: "_Run") -> OrchestratorResult:
        """Original `course_launch` contract (kept so existing code and tests keep working).

        Takes explicit course data (course, level, learning_outcomes, duration_hours, description,
        target_audience, price, output_dir), runs curriculum -> document -> marketing and returns
        `result.output = {"stages": {name: {"ok", "message", "output"}}, "curriculum", "document", "marketing"}`.
        The curriculum must succeed first; a failed PDF does not stop the marketing step; the
        campaign always stays pending admin approval (never approved or published here).
        """
        p = run.params
        title = str(p.get("course") or "").strip()
        stages: dict[str, dict] = {}
        output: dict = {"stages": stages}

        def stage(name: str, label: str, agent: str, task: dict) -> AgentResult:
            res = run.step(label, agent, task)
            stages[name] = {"ok": res.ok, "message": res.message, "output": res.output}
            return res

        def done(ok: bool, message: str) -> OrchestratorResult:
            return OrchestratorResult(ok, "course_launch", message, steps=run.steps, context=run.context,
                                      artifacts={k: v for k, v in output.items() if k != "stages"}, output=output)

        cur = stage("curriculum", "Design the curriculum", "curriculum", {
            "action": "generate", "course": title, "level": p.get("level") or "Beginner",
            "duration_hours": p.get("duration_hours") or 24, "learning_outcomes": p.get("learning_outcomes") or [],
            "language": p.get("language") or "en", "use_llm": bool(p.get("use_llm"))})
        if not cur.ok:
            return done(False, f"Course launch stopped at the curriculum: {cur.message}")
        output["curriculum"] = cur.output
        run.context["curriculum"] = cur.output

        doc = stage("document", "Create the course description PDF", "document", {
            "document_type": "course_description", "curriculum": cur.output,
            "title": title, "description": p.get("description", ""),
            "language": cur.output.get("language", "en"),
            "output_dir": str(p.get("output_dir") or self.docs_dir)})
        if doc.ok:
            output["document"] = doc.output

        course = {"title": title, "description": p.get("description", ""),
                  "target_audience": p.get("target_audience", ""), "price": p.get("price"),
                  "duration_hours": p.get("duration_hours"), "level": p.get("level") or "Beginner",
                  "learning_outcomes": p.get("learning_outcomes") or []}
        mkt = stage("marketing", "Write the campaign", "marketing", {
            "course": course, "curriculum": cur.output, "language": p.get("language") or "en",
            "channels": p.get("channels") or ["instagram", "facebook", "linkedin", "email", "whatsapp"],
            "variations": p.get("variations", 2), "use_llm": bool(p.get("use_llm")),
            "objective": p.get("objective", "leads")})
        if mkt.ok:
            output["marketing"] = mkt.output
            run.context["campaign"] = mkt.output

        failed = [n for n, st in stages.items() if not st["ok"]]
        if failed:
            return done(False, "Course launch finished with problems in: " + ", ".join(failed) + ". "
                        + "; ".join(f"{n}: {stages[n]['message']}" for n in failed))
        return done(True, f"Course launch prepared for {title}: curriculum, PDF and marketing content created. "
                          "The marketing content is pending admin approval and has not been published.")

    def _wf_rfp(self, run: "_Run") -> OrchestratorResult:
        p = run.params
        task = {"discover": bool(p.get("discover", True)), "opportunities": p.get("opportunities") or [],
                "csv_path": str(self.docs_dir / "rfps.csv")}
        if p.get("today"):
            task["today"] = p["today"]
        if p.get("store_path"):
            task["store_path"] = p["store_path"]
        res = run.step("Search and filter RFPs (Egypt + Saudi Arabia only)", "rfp_research", task)
        if not res.ok:
            return run.finish(False, res.message)
        run.context["rfp"] = res.output
        artifacts = {"rfp": res.output}
        msg = (f"Found {res.output['count']} eligible opportunities: "
               f"{len(res.output['flagged_for_immediate_review'])} in Egypt (review now), "
               f"{len(res.output['monitored_pipeline'])} in Saudi Arabia (monitor).")
        recipients = p.get("recipients") or p.get("emails")
        if recipients and res.output["count"]:
            mail = run.step("Prepare the e-mail digest", "rfp_email", {
                "rfp_result": res.output, "recipients": recipients, "send": bool(p.get("send") or p.get("send_email")),
                "language": p.get("language") or "en", "attach_csv": res.output.get("csv_path"),
                "only_new": bool(p.get("only_new"))})
            artifacts["email"] = mail.output
            msg += " " + mail.message
        return run.finish(True, msg, artifacts=artifacts)


class _Stop(Exception):
    def __init__(self, result: OrchestratorResult):
        self.result = result


class _Run:
    """Bookkeeping for one workflow run: records every step it performs."""

    def __init__(self, orch: Orchestrator, intent: str, params: dict, context: dict):
        self.orch, self.intent, self.params, self.context = orch, intent, params, context
        self.steps: list[dict] = []
        self.info: dict = {}

    def step(self, label: str, agent: str, task: dict) -> AgentResult:
        result = self.orch._run_agent(agent, task)
        self.steps.append({"step": label, "agent": agent, "ok": result.ok, "message": result.message})
        return result

    def finish(self, ok: bool, message: str, artifacts: dict | None = None, awaiting: str | None = None,
               needs_input: list[str] | None = None) -> OrchestratorResult:
        return OrchestratorResult(ok, self.intent, message, steps=self.steps, artifacts=artifacts or {},
                                  awaiting=awaiting, needs_input=needs_input or [], context=self.context)
