import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .base import Agent, AgentResult

RAG_DIR = Path(__file__).resolve().parents[2] / "data" / "rag_docs"

# Used by the template (no-LLM) generator so the level really changes the content.
LEVEL_PROFILES = {
    "Beginner": {
        "extra_topics": ["Key concepts and terminology", "Guided hands-on exercise"],
        "exercise": "Step-by-step guided lab with instructor support",
        "prerequisites": "None - suitable for newcomers",
        "assessments": ["Weekly quizzes", "Guided mini-project"],
        "capstone": "A small, guided project that applies every module",
    },
    "Intermediate": {
        "extra_topics": ["Core techniques in practice", "Real-world case study"],
        "exercise": "Practical lab solving a realistic problem with limited guidance",
        "prerequisites": "Basic knowledge of {course} fundamentals",
        "assessments": ["Practical lab assessments", "Case-study report"],
        "capstone": "An independent project solving a realistic business problem",
    },
    "Advanced": {
        "extra_topics": [
            "Advanced techniques and optimization",
            "Design trade-offs and best practices",
            "Industry-scale case study",
        ],
        "exercise": "Open-ended project with design review and peer critique",
        "prerequisites": "Hands-on professional experience in {course} or an intermediate course",
        "assessments": ["Design review", "Written technical exam", "Peer code/design critique"],
        "capstone": "A production-grade project with a design document and final presentation",
    },
}


LEVEL_PROFILES_AR = {
    "Beginner": {
        "extra_topics": ["المفاهيم والمصطلحات الأساسية", "تمرين عملي موجّه"],
        "exercise": "معمل عملي خطوة بخطوة بمساندة المدرّب",
        "prerequisites": "لا توجد متطلبات - مناسبة للمبتدئين",
        "assessments": ["اختبارات قصيرة أسبوعية", "مشروع مصغّر موجّه"],
        "capstone": "مشروع صغير موجّه يطبّق ما تعلّمه المتدرب في جميع الوحدات",
    },
    "Intermediate": {
        "extra_topics": ["التقنيات الأساسية في التطبيق", "دراسة حالة واقعية"],
        "exercise": "معمل عملي لحل مشكلة واقعية بإرشاد محدود",
        "prerequisites": "معرفة أساسية بمبادئ {course}",
        "assessments": ["تقييمات عملية في المعمل", "تقرير دراسة حالة"],
        "capstone": "مشروع مستقل لحل مشكلة عمل واقعية",
    },
    "Advanced": {
        "extra_topics": ["التقنيات المتقدمة والتحسين", "المفاضلات التصميمية وأفضل الممارسات", "دراسة حالة على نطاق مؤسسي"],
        "exercise": "مشروع مفتوح مع مراجعة تصميم ونقد من الزملاء",
        "prerequisites": "خبرة مهنية عملية في {course} أو إتمام دورة متوسطة",
        "assessments": ["مراجعة التصميم", "اختبار تقني كتابي", "نقد الأقران للمشروع"],
        "capstone": "مشروع بمستوى الإنتاج مع وثيقة تصميم وعرض نهائي",
    },
}

ALLOWED_OPS = {"add_module", "remove_module", "rename_module", "set_hours", "add_topic", "set_capstone",
               "add_assessment", "set_prerequisites", "set_total_hours", "add_objective"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _rag_docs(course: str) -> list[tuple[str, str]]:
    """(path, text) of knowledge-base docs that mention the full course title.

    Matching is on the course title, never on the level, so unrelated docs are not
    pulled in.
    """
    needle = course.strip().casefold()
    if not needle or not RAG_DIR.exists():
        return []
    found = []
    try:
        for md_file in sorted(RAG_DIR.glob("*.md")):
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            if needle in text.casefold():
                found.append((f"data/rag_docs/{md_file.name}", text))
    except OSError:
        return []
    return found


def _is_text_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


class CurriculumAgent(Agent):
    name = "curriculum"

    def __init__(self, llm=None):
        """`llm` is any callable(messages) -> str. Only used when a task sets use_llm=True.

        When omitted, the client from .env (LLM_API_KEY ...) is loaded on first use.
        """
        self._llm = llm

    def _get_llm(self):
        if self._llm is None:
            try:
                from rex.rag.llm import LLMClient
                self._llm = LLMClient.from_env()
            except Exception:
                self._llm = None
        return self._llm

    def run(self, task: dict) -> AgentResult:
        action = task.get("action", "validate")

        if action == "generate":
            return self.generate(task)

        if action == "gap_analysis":
            return self.gap_analysis(task)

        if action == "validate":
            return self.validate(task)

        if action == "revise":
            return self.revise(task)

        if action in ("approve", "request_changes"):
            return self.review(task, action)

        return AgentResult(
            self.name,
            False,
            message="Choose action: generate, revise, approve, request_changes, gap_analysis or validate."
        )

    def generate(self, task: dict) -> AgentResult:
        course = task.get("course")
        level = task.get("level", "Beginner")
        outcomes = task.get("learning_outcomes")
        duration = task.get("duration_hours", 12)

        if not isinstance(course, str) or not course.strip():
            return AgentResult(
                self.name, False, message="Please provide a course title."
            )

        if not isinstance(outcomes, list) or not outcomes:
            return AgentResult(
                self.name, False,
                message="Provide learning_outcomes as a non-empty list."
            )

        if not all(isinstance(item, str) and item.strip() for item in outcomes):
            return AgentResult(
                self.name, False,
                message="Every learning outcome must be a non-empty string."
            )

        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            return AgentResult(
                self.name, False,
                message="duration_hours must be a positive number."
            )

        language = str(task.get("language", "en")).lower()
        if language not in ("en", "ar"):
            return AgentResult(self.name, False, message="language must be 'en' or 'ar'.")

        outcomes = [item.strip() for item in outcomes]  # new list: caller's data is untouched
        hours_per_module = round(duration / len(outcomes), 2)
        profiles = LEVEL_PROFILES_AR if language == "ar" else LEVEL_PROFILES
        profile = profiles.get(level, profiles["Beginner"])
        docs = _rag_docs(course)

        plan = None
        generated_by = "template"
        note = ""
        if task.get("use_llm"):
            plan, note = self._llm_plan(course.strip(), level, outcomes, duration, docs, language)
            if plan:
                generated_by = "llm"

        if plan is None:
            plan = self._template_plan(course.strip(), outcomes, profile, language)

        modules = [
            {
                "module": index,
                "title": outcome,
                "topics": plan["modules"][index - 1]["topics"],
                "duration_hours": hours_per_module,
                "activity": plan["modules"][index - 1]["exercise"],
            }
            for index, outcome in enumerate(outcomes, start=1)
        ]

        output = {
            "course": course.strip(),
            "level": level,
            "duration_hours": duration,
            "learning_outcomes": outcomes,
            "objectives": plan["objectives"],
            "prerequisites": plan["prerequisites"],
            "modules": modules,
            "assessments": plan["assessments"],
            "capstone": plan["capstone"],
            "generated_by": generated_by,
            "language": language,
            "version": 1,
            "status_code": "draft",
            "history": [{"event": "generated", "version": 1, "at": _now()}],
            "status": (
                "Proposed curriculum (AI-generated from the academy knowledge base) - requires expert review"
                if generated_by == "llm"
                else "Proposed curriculum - requires expert review"
            ),
        }

        message = f"Generated a proposed curriculum for {course.strip()} ({level})."
        if note:
            message += f" {note}"

        return AgentResult(
            self.name,
            True,
            output=output,
            message=message,
            sources=[path for path, _ in docs],
        )

    @staticmethod
    def _template_plan(course, outcomes, profile, language="en"):
        """Deterministic plan; the level profile decides depth, prerequisites and assessments.

        `topics` starts with the outcome itself so gap_analysis can match it exactly.
        """
        return {
            "objectives": ([f"أن يكون المتدرب قادراً على: {o}" for o in outcomes] if language == "ar"
                           else [f"Be able to: {o[0].lower()}{o[1:]}" for o in outcomes]),
            "prerequisites": profile["prerequisites"].format(course=course),
            "modules": [
                {"topics": [o] + profile["extra_topics"], "exercise": profile["exercise"]}
                for o in outcomes
            ],
            "assessments": list(profile["assessments"]),
            "capstone": profile["capstone"],
        }

    def _llm_plan(self, course, level, outcomes, duration, docs, language="en"):
        """Ask the LLM for the plan. Returns (plan | None, note). Never raises."""
        llm = self._get_llm()
        if llm is None:
            return None, "(AI mode unavailable - no LLM key configured; used the template.)"

        context = "\n\n".join(f"[{path}]\n{text[:1200]}" for path, text in docs[:3])
        system = (
            "You are a curriculum designer for a training academy. Reply with ONE JSON object only, "
            'with keys: "objectives" (list of strings), "prerequisites" (string), '
            '"modules" (list, exactly one item per learning outcome, in the given order, each '
            '{"topics": [3-5 short topic strings], "exercise": string}), '
            '"assessments" (list of strings), "capstone" (string). '
            "Adapt depth, prerequisites, exercises, assessments and capstone to the stated level. "
            "Use the academy context when it is relevant; do not invent fees, instructors or "
            "accreditation claims."
            + (" Write every string value in clear Modern Standard Arabic." if language == "ar" else "")
        )
        user = (
            f"Course: {course}\nLevel: {level}\nTotal hours: {duration}\n"
            "Learning outcomes (one module each):\n"
            + "\n".join(f"{i}. {o}" for i, o in enumerate(outcomes, 1))
            + (f"\n\nAcademy context:\n{context}" if context else "")
        )
        try:
            raw = llm([{"role": "system", "content": system}, {"role": "user", "content": user}])
            match = re.search(r"\{.*\}", raw or "", re.S)  # tolerate prose / code fences
            data = json.loads(match.group(0)) if match else None
        except Exception as error:
            return None, f"(AI mode failed: {error}; used the template.)"

        try:
            modules = data["modules"]
            ok = (
                isinstance(modules, list) and len(modules) == len(outcomes)
                and all(isinstance(m, dict) and _is_text_list(m.get("topics"))
                        and isinstance(m.get("exercise"), str) for m in modules)
                and _is_text_list(data["objectives"]) and _is_text_list(data["assessments"])
                and isinstance(data["prerequisites"], str) and isinstance(data["capstone"], str)
            )
        except (TypeError, KeyError):
            ok = False
        if not ok:
            return None, "(AI reply was not in the expected format; used the template.)"

        plan = {
            "objectives": data["objectives"],
            "prerequisites": data["prerequisites"],
            "assessments": data["assessments"],
            "capstone": data["capstone"],
            "modules": [],
        }
        for outcome, m in zip(outcomes, modules):
            topics = [t.strip() for t in m["topics"]]
            if outcome.casefold() not in (t.casefold() for t in topics):
                topics.insert(0, outcome)  # keep gap analysis matching on the outcome
            plan["modules"].append({"topics": topics, "exercise": m["exercise"].strip()})
        return plan, ""

    def gap_analysis(self, task: dict) -> AgentResult:
        required_topics = task.get("required_topics")
        curriculum = task.get("curriculum")

        if not isinstance(required_topics, list) or not required_topics:
            return AgentResult(
                self.name, False,
                message="Provide a non-empty required_topics list."
            )

        if not isinstance(curriculum, list):
            return AgentResult(
                self.name, False,
                message="Provide curriculum as a list of course objects."
            )

        actual_topics = []

        for course in curriculum:
            if not isinstance(course, dict):
                return AgentResult(
                    self.name, False,
                    message="Each curriculum item must be a course object."
                )

            topics = course.get("topics", [])

            if not isinstance(topics, list):
                return AgentResult(
                    self.name, False,
                    message="Course topics must be a list."
                )

            actual_topics.extend(
                topic.casefold().strip()
                for topic in topics
                if isinstance(topic, str)
            )

        missing_topics = [
            topic for topic in required_topics
            if isinstance(topic, str)
            and topic.casefold().strip() not in actual_topics
        ]

        output = {
            "required_topics": required_topics,
            "covered_topics": [
                topic for topic in required_topics
                if isinstance(topic, str)
                and topic.casefold().strip() in actual_topics
            ],
            "missing_topics": missing_topics,
            "coverage_percentage": round(
                100 * (len(required_topics) - len(missing_topics))
                / len(required_topics), 2
            ),
            "accreditation_status": "Not assessed"
        }

        return AgentResult(
            self.name,
            True,
            output=output,
            message=(
                f"Gap analysis complete. "
                f"Found {len(missing_topics)} missing topic(s)."
            ),
            sources=[]
        )

    def validate(self, task: dict) -> AgentResult:
        curriculum = task.get("curriculum", [])

        if not isinstance(curriculum, list) or not curriculum:
            return AgentResult(
                self.name, False,
                message="Please provide a non-empty curriculum list."
            )

        required_fields = ["course", "topics"]
        issues = []
        reviewed_courses = []

        for index, course in enumerate(curriculum, start=1):
            if not isinstance(course, dict):
                issues.append(f"Item {index} must be a course object.")
                continue

            missing_fields = [
                field for field in required_fields
                if field not in course
            ]

            if missing_fields:
                issues.append(
                    f"Item {index} is missing: {', '.join(missing_fields)}."
                )
                continue

            topics = course["topics"]

            if not isinstance(topics, list):
                issues.append(
                    f"{course['course']}: topics must be a list."
                )
                continue

            if not topics:
                issues.append(
                    f"{course['course']}: no topics have been provided."
                )

            reviewed_courses.append({
                "course": course["course"],
                "topic_count": len(topics),
                "topics": topics
            })

        output = {
            "reviewed_courses": reviewed_courses,
            "issues": issues,
            "course_count": len(reviewed_courses),
            "accreditation_status": "Not assessed"
        }

        return AgentResult(
            self.name,
            True,
            output=output,
            message=(
                f"Reviewed {len(reviewed_courses)} course(s). "
                f"Found {len(issues)} issue(s). "
                "This is a curriculum structure review, not an official "
                "accreditation assessment."
            ),
            sources=[]
        )

    # ------------------------------------------------------- review loop
    def revise(self, task: dict) -> AgentResult:
        """Apply reviewer feedback to a curriculum and return a new version (status: in_review).

        Give structured `changes` (list of {"op": ...}) and/or a plain-language `instruction`
        (English or Arabic; understood by the AI when `use_llm` is set, otherwise by simple rules).
        """
        current = task.get("curriculum")
        if not isinstance(current, dict) or not isinstance(current.get("modules"), list) or not current["modules"]:
            return AgentResult(self.name, False, message="Provide the curriculum (generate output) to revise.")

        ops = [op for op in (task.get("changes") or []) if isinstance(op, dict)]
        instruction = str(task.get("instruction") or "").strip()
        note = ""
        if instruction:
            parsed = []
            if task.get("use_llm"):
                parsed, note = self._llm_ops(current, instruction)
            if not parsed:
                parsed = self._rule_ops(instruction)
            ops += parsed
        if not ops:
            return AgentResult(
                self.name, False,
                message="I could not turn that into a change. Try: 'add module Data ethics 4 hours', "
                        "'remove module 2', 'rename module 1 to ...', 'set capstone: ...', 'total hours 50'.")

        updated = deepcopy(current)
        applied, skipped = [], []
        for op in ops:
            message = self._apply_op(updated, op)
            (applied if message.startswith("ok:") else skipped).append(message.split(": ", 1)[1])
        if not applied:
            return AgentResult(self.name, False, message="No change could be applied: " + "; ".join(skipped))

        for index, module in enumerate(updated["modules"], start=1):
            module["module"] = index
        updated["learning_outcomes"] = [m["title"] for m in updated["modules"]]
        if not any(o.get("op") == "set_total_hours" for o in ops):
            updated["duration_hours"] = round(sum(float(m.get("duration_hours", 0)) for m in updated["modules"]), 2)
        updated["version"] = int(current.get("version", 1)) + 1
        updated["status_code"] = "in_review"
        updated["status"] = "Revised curriculum - awaiting expert approval"
        updated.pop("approved_by", None)
        updated.pop("approved_at", None)
        updated.setdefault("history", []).append(
            {"event": "revised", "version": updated["version"], "at": _now(), "changes": applied})
        message = f"Curriculum revised (version {updated['version']}): " + "; ".join(applied) + "."
        if skipped:
            message += " Skipped: " + "; ".join(skipped) + "."
        if note:
            message += " " + note
        return AgentResult(self.name, True, output=updated, message=message,
                           sources=list(task.get("sources") or []))

    def review(self, task: dict, action: str) -> AgentResult:
        """Approve a curriculum or send it back with comments. Needs a named reviewer."""
        current = task.get("curriculum")
        if not isinstance(current, dict) or not current.get("modules"):
            return AgentResult(self.name, False, message="Provide the curriculum to review.")
        reviewer = str(task.get("reviewer", "")).strip()
        if not reviewer:
            return AgentResult(self.name, False, message="A reviewer name is required.")
        note = str(task.get("note", "")).strip()
        if action == "request_changes" and not note:
            return AgentResult(self.name, False, message="Describe the changes you want in `note`.")

        updated = deepcopy(current)
        if action == "approve":
            updated["status_code"] = "approved"
            updated["approved_by"] = reviewer
            updated["approved_at"] = _now()
            updated["status"] = (f"Approved by {reviewer} for internal use. This is not an official "
                                 "accreditation.")
            event = {"event": "approved", "by": reviewer, "at": updated["approved_at"], "note": note}
            message = f"Curriculum approved by {reviewer}."
        else:
            updated["status_code"] = "changes_requested"
            updated["status"] = f"Changes requested by {reviewer}"
            event = {"event": "changes_requested", "by": reviewer, "at": _now(), "note": note}
            message = f"Changes requested by {reviewer}: {note}"
        updated.setdefault("history", []).append(event)
        return AgentResult(self.name, True, output=updated, message=message)

    # ---- helpers for revise()
    @staticmethod
    def _apply_op(c: dict, op: dict) -> str:
        kind = op.get("op")
        modules = c["modules"]

        def module_at(value):
            try:
                i = int(value) - 1
            except (TypeError, ValueError):
                return None
            return modules[i] if 0 <= i < len(modules) else None

        def number(value):
            try:
                n = float(value)
            except (TypeError, ValueError):
                return None
            return n if n > 0 else None

        if kind not in ALLOWED_OPS:
            return f"skip: unknown change '{kind}'"
        if kind == "add_module":
            title = str(op.get("title", "")).strip()
            if not title:
                return "skip: add_module needs a title"
            hours = number(op.get("hours")) or round(
                sum(float(m.get("duration_hours", 0)) for m in modules) / len(modules), 2)
            topics = [str(t).strip() for t in (op.get("topics") or []) if str(t).strip()] or [title]
            modules.append({"module": len(modules) + 1, "title": title, "topics": topics,
                            "duration_hours": hours, "activity": modules[-1].get("activity", "")})
            return f"ok: added module '{title}' ({hours:g} h)"
        if kind in ("remove_module", "rename_module", "set_hours", "add_topic"):
            module = module_at(op.get("index"))
            if module is None:
                return f"skip: module {op.get('index')} does not exist"
            if kind == "remove_module":
                if len(modules) == 1:
                    return "skip: a curriculum needs at least one module"
                modules.remove(module)
                return f"ok: removed module '{module['title']}'"
            if kind == "rename_module":
                new = str(op.get("title", "")).strip()
                if not new:
                    return "skip: rename needs a title"
                old, module["title"] = module["title"], new
                return f"ok: renamed '{old}' to '{new}'"
            if kind == "set_hours":
                hours = number(op.get("hours"))
                if hours is None:
                    return "skip: hours must be a positive number"
                module["duration_hours"] = hours
                return f"ok: module {op['index']} now {hours:g} h"
            topic = str(op.get("topic", "")).strip()
            if not topic:
                return "skip: add_topic needs a topic"
            module.setdefault("topics", []).append(topic)
            return f"ok: added topic '{topic}' to module {op['index']}"
        if kind == "set_total_hours":
            total = number(op.get("hours"))
            if total is None:
                return "skip: total hours must be a positive number"
            current = sum(float(m.get("duration_hours", 0)) for m in modules) or 1
            for m in modules:
                m["duration_hours"] = round(float(m.get("duration_hours", 0)) * total / current, 2)
            c["duration_hours"] = total
            return f"ok: total duration scaled to {total:g} h"
        text = str(op.get("text", "")).strip()
        if not text:
            return f"skip: {kind} needs text"
        if kind == "set_capstone":
            c["capstone"] = text
        elif kind == "set_prerequisites":
            c["prerequisites"] = text
        elif kind == "add_assessment":
            c.setdefault("assessments", []).append(text)
        elif kind == "add_objective":
            c.setdefault("objectives", []).append(text)
        return f"ok: {kind.replace('_', ' ')}"

    @staticmethod
    def _rule_ops(instruction: str) -> list[dict]:
        """Understand a few common phrases in English and Arabic (no AI needed)."""
        text = instruction.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        ops = []
        for line in re.split(r"[\n;]+", text):
            line = line.strip().rstrip(".")
            if not line:
                continue
            low = line.lower()
            num = r"(\d+(?:\.\d+)?)"
            if m := re.match(r"(?:please )?add (?:a |one )?(?:new )?module(?: on| about| for| called| named)? (.+?)(?: (?:for |of |with )?" + num + r" ?(?:hours?|h))?$", low):
                title = line[m.start(1):m.end(1)].strip(" :-")
                ops.append({"op": "add_module", "title": title, "hours": m.group(2)})
            elif m := re.match(r"أضف (?:وحدة|موديول)(?: عن| حول| بعنوان)? (.+?)(?: " + num + r" ?ساعة?)?$", line):
                ops.append({"op": "add_module", "title": m.group(1).strip(" :-"), "hours": m.group(2)})
            elif m := re.match(r"(?:remove|delete|drop) module " + num + r"$", low) or \
                    re.match(r"(?:احذف|أزل|امسح) (?:الوحدة|وحدة|الموديول) " + num + r"$", line):
                ops.append({"op": "remove_module", "index": m.group(1)})
            elif m := re.match(r"rename module " + num + r" (?:to|as) (.+)$", low):
                ops.append({"op": "rename_module", "index": m.group(1), "title": line[m.start(2):].strip()})
            elif m := re.match(r"(?:set )?module " + num + r"(?: to| =)? " + num + r" ?(?:hours?|h)$", low):
                ops.append({"op": "set_hours", "index": m.group(1), "hours": m.group(2)})
            elif m := re.match(r"(?:set )?(?:total|course) (?:hours|duration)(?: to|:)? " + num + r"(?: ?hours?)?$", low) or \
                    re.match(r"(?:اجعل|غير|غيّر) (?:المدة|الساعات)(?: الى| إلى)? " + num + r"(?: ساعة)?$", line):
                ops.append({"op": "set_total_hours", "hours": m.group(1)})
            elif m := re.match(r"(?:set )?capstone(?: project)?(?: to)?[:\-]? (.+)$", line, re.I) or \
                    re.match(r"(?:المشروع النهائي|مشروع التخرج)[:\-]? (.+)$", line):
                ops.append({"op": "set_capstone", "text": m.group(1).strip()})
            elif m := re.match(r"add assessment[:\-]? (.+)$", line, re.I):
                ops.append({"op": "add_assessment", "text": m.group(1).strip()})
            elif m := re.match(r"(?:set )?prerequisites?(?: to)?[:\-]? (.+)$", line, re.I):
                ops.append({"op": "set_prerequisites", "text": m.group(1).strip()})
        return ops

    def _llm_ops(self, current: dict, instruction: str):
        """Ask the AI to translate the instruction into change operations. Never raises."""
        llm = self._get_llm()
        if llm is None:
            return [], "(AI mode unavailable - used simple rules.)"
        system = (
            "You edit a course curriculum. Reply with ONE JSON object: {\"changes\": [...]}. Each change is one of: "
            '{"op":"add_module","title":str,"topics":[str],"hours":number}, {"op":"remove_module","index":int}, '
            '{"op":"rename_module","index":int,"title":str}, {"op":"set_hours","index":int,"hours":number}, '
            '{"op":"add_topic","index":int,"topic":str}, {"op":"set_capstone","text":str}, '
            '{"op":"add_assessment","text":str}, {"op":"set_prerequisites","text":str}, '
            '{"op":"add_objective","text":str}, {"op":"set_total_hours","hours":number}. '
            "Module indexes start at 1. Use the language of the curriculum for any new text. "
            "Do not add anything the reviewer did not ask for."
        )
        outline = [{"index": m.get("module"), "title": m.get("title"), "hours": m.get("duration_hours")}
                   for m in current["modules"]]
        try:
            raw = llm([{"role": "system", "content": system},
                       {"role": "user", "content": json.dumps(
                           {"modules": outline, "capstone": current.get("capstone"),
                            "instruction": instruction}, ensure_ascii=False)}])
            match = re.search(r"\{.*\}", raw or "", re.S)
            data = json.loads(match.group(0)) if match else {}
            ops = [o for o in data.get("changes", []) if isinstance(o, dict) and o.get("op") in ALLOWED_OPS]
        except Exception as error:
            return [], f"(AI mode failed: {error}; used simple rules.)"
        return ops, ""
