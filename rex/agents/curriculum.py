import json
import re
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

        return AgentResult(
            self.name,
            False,
            message="Choose action: validate, generate, or gap_analysis."
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

        outcomes = [item.strip() for item in outcomes]  # new list: caller's data is untouched
        hours_per_module = round(duration / len(outcomes), 2)
        profile = LEVEL_PROFILES.get(level, LEVEL_PROFILES["Beginner"])
        docs = _rag_docs(course)

        plan = None
        generated_by = "template"
        note = ""
        if task.get("use_llm"):
            plan, note = self._llm_plan(course.strip(), level, outcomes, duration, docs)
            if plan:
                generated_by = "llm"

        if plan is None:
            plan = self._template_plan(course.strip(), outcomes, profile)

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
    def _template_plan(course, outcomes, profile):
        """Deterministic plan; the level profile decides depth, prerequisites and assessments.

        `topics` starts with the outcome itself so gap_analysis can match it exactly.
        """
        return {
            "objectives": [f"Be able to: {o[0].lower()}{o[1:]}" for o in outcomes],
            "prerequisites": profile["prerequisites"].format(course=course),
            "modules": [
                {"topics": [o] + profile["extra_topics"], "exercise": profile["exercise"]}
                for o in outcomes
            ],
            "assessments": list(profile["assessments"]),
            "capstone": profile["capstone"],
        }

    def _llm_plan(self, course, level, outcomes, duration, docs):
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
