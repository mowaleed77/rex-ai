"""REX Assistant conversation engine."""

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .kb import KnowledgeBase, DATA_DIR
from .text import is_arabic, normalize, tokens

LEADS_FILE = DATA_DIR / "leads.csv"

LEVEL_AR = {
    "Beginner": "مبتدئ",
    "Intermediate": "متوسط",
    "Advanced": "متقدم",
}

LEVELS = {
    "Beginner": "beginner none no experience zero start مبتدي مبتدئ جديد",
    "Intermediate": "intermediate some medium متوسط",
    "Advanced": "advanced expert professional متقدم محترف",
}

FORMATS = {
    "online": "online remote اونلاين أونلاين اون لاين عن بعد",
    "onsite": "onsite on-site offline in-person حضوري",
    "hybrid": "hybrid مدمج",
}

YES = set("yes y ok okay sure yep نعم ايوه أيوه اي اه موافق تمام اكيد أكيد".split())
NO = set("no n nope لا مش".split())


T = {
    "greet": (
        "Hello! I'm REX, the academy's course assistant. "
        "Ask me about courses, prices, instructors, or your learning goals.",
        "أهلاً! أنا REX مساعد الأكاديمية. اسألني عن الدورات أو الأسعار "
        "أو المدربين، أو قولي إيه المجال اللي حابب تتعلمه.",
    ),
    "ask_interest": (
        "What topic or career path are you interested in "
        "(e.g. data, AI, web, security, marketing)?",
        "إيه المجال أو المسار الوظيفي اللي مهتم بيه "
        "(مثلاً البيانات، الذكاء الاصطناعي، الويب، الأمن السيبراني أو التسويق)؟",
    ),
    "ask_level": (
        "What's your current level: beginner, intermediate or advanced?",
        "مستواك الحالي إيه: مبتدئ، متوسط ولا متقدم؟",
    ),
    "ask_format": (
        "Do you prefer online or on-site training? "
        "And do you have a budget in EGP?",
        "تفضل التدريب أونلاين ولا حضوري؟ وعندك ميزانية معينة بالجنيه؟",
    ),
    "none": (
        "I couldn't find a matching course in our catalog. "
        "Try another topic, or ask me to list all available courses.",
        "ملقيتش دورة مناسبة في الكتالوج. جرّب مجال تاني، "
        "أو اطلب مني أعرض لك كل الدورات المتاحة.",
    ),
    "consent": (
        "Would you like our admissions team to follow up with you? "
        "(yes/no) — we'll only save your details with your consent.",
        "تحب فريق القبول يتواصل معاك؟ (نعم/لا) — مش هنحفظ بياناتك "
        "غير بموافقتك.",
    ),
    "ask_name": (
        "Great, what's your name?",
        "تمام، اسمك إيه؟",
    ),
    "ask_contact": (
        "Thanks! What's the best phone number or email to reach you?",
        "شكراً! إيه رقم الهاتف أو الإيميل المناسب للتواصل؟",
    ),
    "saved": (
        "Done — your details were saved for follow-up. Anything else I can help with?",
        "تم حفظ بياناتك للمتابعة. أقدر أساعدك في إيه تاني؟",
    ),
    "declined": (
        "No problem, nothing was saved. Ask me anything about the courses.",
        "ولا يهمك، مفيش حاجة اتحفظت. اسألني عن أي دورة.",
    ),
    "help": (
        "You can ask about course prices, duration, instructors, prerequisites, "
        "or learning outcomes. You can also ask for all available courses.",
        "تقدر تسأل عن الأسعار أو المدة أو المدربين أو المتطلبات "
        "أو محتوى الدورات. وتقدر كمان تطلب عرض كل الدورات المتاحة.",
    ),
    "need_course": (
        "Which course do you mean? Tell me its name, or ask me to list all courses.",
        "تقصد أنهي دورة؟ اذكر اسمها، أو اطلب مني أعرض كل الدورات.",
    ),
}



@dataclass
class Session:
    lang: str = "en"
    history: list[dict] = field(default_factory=list)
    interest: list[str] = field(default_factory=list)
    level: str | None = None
    fmt: str | None = None
    budget: int | None = None
    last_courses: list[dict] = field(default_factory=list)
    stage: str = "chat"
    lead: dict = field(default_factory=dict)
    started: bool = False
    language_locked: bool = False
    last_answer: str = ""


class RexAssistant:
    def __init__(
        self,
        kb: KnowledgeBase | None = None,
        leads_file: Path = LEADS_FILE,
    ):
        self.kb = kb or KnowledgeBase()
        self.leads_file = leads_file

    def _t(self, key, s):
        return T[key][1 if s.lang == "ar" else 0]

    @staticmethod
    def _has(text, vocab):
        text_words = set(re.findall(r"\w+", normalize(text)))
        vocab_words = set(re.findall(r"\w+", normalize(vocab)))
        return bool(text_words & vocab_words)

    @staticmethod
    def _requested_language(msg):
        n = normalize(msg).lower()

        arabic_requests = (
            "answer in arabic", "response in arabic", "respond in arabic",
            "reply in arabic", "speak arabic", "switch to arabic",
            "arabic please", "in arabic", "translate to arabic",
            "باللغة العربية", "اتكلم عربي", "رد بالعربي",
            "خليك عربي", "بالعربي", "ترجم للعربي", "ترجم بالعربية",
        )
        english_requests = (
            "answer in english", "response in english", "respond in english",
            "reply in english", "speak english", "switch to english",
            "english please", "in english", "translate to english",
            "باللغة الانجليزية", "بالانجليزي", "اتكلم انجليزي",
            "رد بالانجليزي", "بالإنجليزية", "ترجم للانجليزي",
        )

        if any(phrase in n for phrase in arabic_requests):
            return "ar"
        if any(phrase in n for phrase in english_requests):
            return "en"
        return None

    @staticmethod
    def _is_course_list_request(msg):
        n = normalize(msg).lower()
        patterns = (
            "available course", "all courses", "list courses",
            "show courses", "courses available", "what courses",
            "which courses", "course catalog", "course catalogue",
            "available training", "كل الدورات", "جميع الدورات",
            "الدورات المتاحة", "الكورسات المتاحة", "كل الكورسات",
            "اعرض الدورات", "اعرض الكورسات", "الدورات الموجودة",
            "ما هي الدورات", "ايه الدورات", "ماهي الدورات",
            "الكورسات الموجودة", "الدورات عندكم",
        )
        return any(pattern in n for pattern in patterns)

    @staticmethod
    def _is_price_list_request(msg):
        n = normalize(msg).lower()
        return any(
            phrase in n
            for phrase in (
                "prices", "price list", "all prices", "course prices",
                "how much are", "what are the prices", "fees for all",
                "الاسعار", "الأسعار", "اسعار الدورات", "أسعار الدورات",
                "اسعار الكورسات", "أسعار الكورسات", "بكام الدورات",
                "بكام الكورسات", "سعر كل دورة", "سعر كل كورس",
            )
        )

    @staticmethod
    def _is_translation_request(msg):
        n = normalize(msg).lower()
        return any(
            phrase in n
            for phrase in (
                "translate that", "translate it", "translate your answer",
                "translate the previous", "ترجم الرد", "ترجم الاجابة",
                "ترجم الإجابة", "ترجم كلامك", "ترجم اللي فات",
            )
        )

    def _update_slots(self, s: Session, msg: str):
        for level, vocab in LEVELS.items():
            if self._has(msg, vocab):
                s.level = level
                break

        for fmt, vocab in FORMATS.items():
            if self._has(msg, vocab):
                s.fmt = fmt
                break

        match = re.search(r"(\d[\d,]{2,})\s*(egp|le|جنيه|ج)?", msg.lower())
        if match:
            s.budget = int(match.group(1).replace(",", ""))

        slot_vocab = " ".join(list(LEVELS.values()) + list(FORMATS.values()))
        slot_tokens = set(tokens(slot_vocab))
        new_tokens = [
            token
            for token in tokens(msg)
            if token not in slot_tokens and not token.isdigit()
        ]

        # Avoid treating generic conversation words as a new topic.
        ignored = set(tokens(
            "i want learn course courses available show list all please "
            "what which are the about price prices cost fees much "
            "recommend recommendation for me my current level "
            "عايز عايزة اريد اريد ان اعرف ما هي ايه اي الدورات الكورسات "
            "المتاحة عندكم اسعار الاسعار بكام من فضلك"
        ))
        new_tokens = [token for token in new_tokens if token not in ignored]

        if new_tokens:
            # Only reset the previous recommendations when the user introduces
            # a genuinely different topic with a matching catalog result.
            query = " ".join(new_tokens)
            hits = self.kb.search(query, top_k=3)
            if hits and s.last_courses:
                old_ids = {c["id"] for c in s.last_courses}
                new_ids = {c["id"] for _, c in hits}
                if not (old_ids & new_ids):
                    s.last_courses = []
                    s.interest = []

            s.interest.extend(new_tokens)
            s.interest = list(dict.fromkeys(s.interest))

    def _course_list(self, s: Session, courses=None):
        courses = self.kb.courses if courses is None else courses
        if not courses:
            return self._t("none", s)

        arabic = s.lang == "ar"
        lines = [
            "الدورات المتاحة في الأكاديمية:"
            if arabic else "Available courses in the academy:"
        ]

        for i, course in enumerate(courses, 1):
            title = course["title_ar"] if arabic else course["title_en"]
            level = LEVEL_AR.get(course.get("level"), course.get("level", ""))
            duration = course.get("duration_hours", "?")
            price = f"{course.get('price_egp', 0):,}"
            if arabic:
                meta = f"{level} | {duration} ساعة | {price} جنيه"
            else:
                meta = f"{course.get('level', 'N/A')} | {duration} hours | {price} EGP"
            formats = ", ".join(course.get("formats", []))
            lines.append(f"{i}. {title}\n   {meta} | {formats}")

        lines.append(
            "\nاسألني عن سعر أو تفاصيل أي دورة."
            if arabic else "\nAsk me about the price or details of any course."
        )
        s.last_courses = list(courses)
        return "\n".join(lines)

    def _price_list(self, s: Session):
        courses = s.last_courses or self.kb.courses
        arabic = s.lang == "ar"
        lines = [
            "أسعار الدورات:"
            if arabic else "Course prices:"
        ]

        for i, course in enumerate(courses, 1):
            title = course["title_ar"] if arabic else course["title_en"]
            price = f"{course.get('price_egp', 0):,}"
            line = (
                f"{i}. {title}: {price} جنيه"
                if arabic else f"{i}. {title}: {price} EGP"
            )
            promotion = course.get("promotion")
            if promotion and promotion != "None":
                line += f" â€” {promotion}"
            lines.append(line)

        return "\n".join(lines)

    def _course_question(self, s: Session, msg: str):
        normalized_msg = normalize(msg)
        course = self.kb.find_course(msg)

        # If the user asks about a property without naming a course, use the
        # last recommendation(s) instead of starting the recommendation flow.
        asks = {
            "price": (
                "price prices cost fee fees much offer offers promotion discount "
                "سعر اسعار الأسعار تكلفه رسوم عرض خصم بكام"
            ),
            "duration": "duration hours long مدة مده ساعات",
            "instructor": "instructor trainer teacher teaches teach مدرب محاضر",
            "prereq": "prerequisite prerequisites requirements متطلبات شروط",
            "outcomes": "outcomes content syllabus topics محتوى محتوي مخرجات هتعلم",
            "audience": "audience career careers jobs وظائف وظايف فرص",
        }

        kind = next(
            (
                key for key, vocabulary in asks.items()
                if self._has(normalized_msg, vocabulary)
            ),
            None,
        )

        if kind is None:
            return None

        if not course and not s.last_courses:
            return self._t("need_course", s)

        courses = [course] if course else s.last_courses
        arabic = s.lang == "ar"
        lines = []

        for item in courses:
            name = item["title_ar"] if arabic else item["title_en"]

            if kind == "price":
                price = f"{item.get('price_egp', 0):,}"
                result = f"{name}: {price} جنيه" if arabic else f"{name}: {price} EGP"
                promotion = item.get("promotion")
                if promotion and promotion != "None":
                    result += f" â€” {promotion}"
                lines.append(result)

            elif kind == "duration":
                unit = "ساعة" if arabic else "hours"
                formats = ", ".join(item.get("formats", []))
                lines.append(f"{name}: {item.get('duration_hours', '?')} {unit}, {formats}")

            elif kind == "instructor":
                instructor = self.kb.instructors.get(item.get("instructor_id"), {})
                instructor_name = (
                    instructor.get("title_ar") or instructor.get("name", "غير محدد")
                    if arabic else instructor.get("name", "Not specified")
                )
                experience = instructor.get("experience_years")
                bio = instructor.get("bio", "")
                unit = "سنة خبرة" if arabic else "years of experience"
                result = f"{name}: {instructor_name}"
                if experience is not None:
                    result += f" â€” {experience} {unit}"
                if bio:
                    result += f". {bio}"
                lines.append(result)

            elif kind == "prereq":
                lines.append(f"{name}: {item.get('prerequisites', 'غير محدد' if arabic else 'Not specified')}")

            elif kind == "outcomes":
                outcomes = item.get("learning_outcomes", [])
                lines.append(f"{name}: " + "; ".join(outcomes))

            elif kind == "audience":
                careers = item.get("career_opportunities", [])
                audience = item.get("target_audience", "")
                lines.append(f"{name}: {audience} | " + ", ".join(careers))

        return "\n".join(lines)

    @staticmethod
    def _course_level(course):
        levels = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
        return levels.get(course.get("level"), 1)

    def _recommend(self, s: Session):
        hits = self.kb.search(" ".join(s.interest), top_k=8)
        ranked = []

        for score, course in hits:
            course_level = self._course_level(course)
            user_level = self._course_level({"level": s.level}) if s.level else 0
            gap = course_level - user_level
            bonus = 2 if gap == 0 else (-3 * gap if gap > 0 else -1)

            title = (course.get("title_en", "") + " " + course.get("title_ar", "")).lower()
            interest_text = " ".join(s.interest).lower()
            beginner_ai_request = (
                s.level == "Beginner"
                and self._has(interest_text, "AI artificial intelligence ذكاء اصطناعي الذكاء الاصطناعي")
            )
            is_python_beginner_course = (
                "python for data analysis" in title
                or "بايثون لتحليل البيانات" in title
            )

            if beginner_ai_request and is_python_beginner_course:
                bonus += 10

            if s.fmt and s.fmt not in course.get("formats", []):
                bonus -= 3
            if s.budget and course.get("price_egp", 0) > s.budget:
                bonus -= 3

            ranked.append((score + bonus, course))

        ranked.sort(key=lambda item: item[0], reverse=True)

        if not ranked:
            s.last_courses = []
            return self._t("none", s)

        selected = ranked[:3]

        interest_text = " ".join(s.interest)
        if s.level == "Beginner" and self._has(
    interest_text,
    "AI artificial intelligence ذكاء اصطناعي الذكاء الاصطناعي",
):
            for index, (_, course) in enumerate(selected):
                title = (course.get("title_en", "") + " " + course.get("title_ar", "")).lower()
                if (
    "python for data analysis" in title
    or "بايثون لتحليل البيانات" in title
):
                    selected.insert(0, selected.pop(index))
                    break

        courses = [course for _, course in selected]
        s.last_courses = courses
        arabic = s.lang == "ar"
        user_level = self._course_level({"level": s.level}) if s.level else 0

        suitable_exists = any(self._course_level(course) <= user_level for course in courses)
        if s.level and not suitable_exists:
            lines = [
                (
                    f"مفيش دورة مناسبة لمستوى {LEVEL_AR[s.level]} في النتائج دي. "
                    "الخيارات التالية أعلى من مستواك:"
                    if arabic else
                    f"We don't have a {s.level} course on this topic yet. "
                    "These are the closest options (above your level):"
                )
            ]
        else:
            lines = [
                "أنسب الدورات ليك:" if arabic else "Here are the best matches for you:"
            ]

        for number, course in enumerate(courses, 1):
            why = []
            course_level = self._course_level(course)
            gap = course_level - user_level

            if s.level == course.get("level"):
                why.append(
                    f"مستواها {LEVEL_AR[course['level']]}"
                    if arabic else f"it's a {course['level']} course matching your level"
                )

            if s.fmt and s.fmt in course.get("formats", []):
                why.append(
                    "متاحة " + {"online": "أونلاين", "onsite": "حضوري", "hybrid": "مدمج"}.get(s.fmt, s.fmt)
                    if arabic else f"available {s.fmt}"
                )

            if s.budget and course.get("price_egp", 0) <= s.budget:
                why.append("ضمن ميزانيتك" if arabic else "within your budget")

            description = course.get("description", "")
            if description:
                why.append(description)

            if gap > 0:
                prerequisites = course.get("prerequisites", "")
                warning = (
                    "ملحوظة: مستواها أعلى من مستواك، والمتطلبات: "
                    if arabic else "Note: above your level â€” prerequisites: "
                )
                if prerequisites:
                    why.append(warning + prerequisites)

            title = course["title_ar"] if arabic else course["title_en"]
            price = f"{course.get('price_egp', 0):,}"
            meta = (
                f"{LEVEL_AR.get(course.get('level'), course.get('level'))}، "
                f"{course.get('duration_hours', '?')} ساعة، {price} جنيه"
                if arabic else
                f"{course.get('level', 'N/A')}, "
                f"{course.get('duration_hours', '?')}h, {price} EGP"
            )

            lines.append(
                f"{number}. {title}\n"
                f"   {meta}\n"
                f"   " + ("السبب: " if arabic else "Why: ")
                + "; ".join(part for part in why if part)
            )

            course_title = (course.get("title_en", "") + " " + course.get("title_ar", "")).lower()
            is_genai_course = (
                "generative ai" in course_title
                or "llm" in course_title
                or "نماذج اللغة" in course_title
            )
            if s.level == "Beginner" and is_genai_course and gap > 0:
                lines.append(
                    "   تنبيه: الدورة أعلى من مستواك. يُفضّل معرفة بايثون وأساسيات تعلم الآلة أولاً."
                    if arabic else
                    "   This course is above your level. You should have Python and basic ML knowledge first."
                )

        lines.append(
            "\nتقدر تسألني عن السعر أو المدرب أو المتطلبات لأي دورة."
            if arabic else
            "\nAsk me about price, instructor, prerequisites or content of any of them."
        )

        s.stage = "consent"
        lines.append(self._t("consent", s))
        return "\n".join(lines)

    def _save_lead(self, s: Session):
        self.leads_file.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.leads_file.exists()

        with open(self.leads_file, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if is_new:
                writer.writerow([
                    "timestamp", "name", "contact", "interest", "level",
                    "format", "budget", "recommended", "consent",
                ])

            writer.writerow([
                datetime.now(timezone.utc).isoformat(),
                s.lead.get("name"),
                s.lead.get("contact"),
                " ".join(dict.fromkeys(s.interest)),
                s.level,
                s.fmt,
                s.budget,
                "|".join(course["id"] for course in s.last_courses),
                "yes",
            ])

    def reply(self, s: Session, msg: str) -> str:
        msg = msg.strip()
        if not msg:
            return self._t("greet", s)

        requested_language = self._requested_language(msg)
        if requested_language:
            s.lang = requested_language
            s.language_locked = True
            if self._is_translation_request(msg) and s.last_answer:
                answer = s.last_answer
            else:
                answer = self._t("greet", s)
            s.last_answer = answer
            return answer

        if not s.language_locked:
            s.lang = "ar" if is_arabic(msg) else "en"

        words = set(re.findall(r"\w+", normalize(msg)))

        # Handle consent/name/contact collection only during the consent flow.
        if s.stage == "consent" and len(words) <= 3:
            if words & {normalize(word) for word in YES}:
                s.stage = "name"
                answer = self._t("ask_name", s)
                s.last_answer = answer
                return answer

            if words & {normalize(word) for word in NO}:
                s.stage = "chat"
                answer = self._t("declined", s)
                s.last_answer = answer
                return answer

        if s.stage == "name":
            s.lead["name"] = msg
            s.stage = "contact"
            answer = self._t("ask_contact", s)
            s.last_answer = answer
            return answer

        if s.stage == "contact":
            s.lead["contact"] = msg
            s.stage = "chat"
            self._save_lead(s)
            answer = self._t("saved", s)
            s.last_answer = answer
            return answer

        first = not s.started
        s.started = True

        # Translate the last answer when explicitly requested.
        if self._is_translation_request(msg) and s.last_answer:
            answer = s.last_answer
            s.last_answer = answer
            return answer

        # List-all and price-list requests should not require a level first.
        if self._is_course_list_request(msg):
            answer = self._course_list(s)
            s.last_answer = answer
            return answer

        if self._is_price_list_request(msg):
            answer = self._price_list(s)
            s.last_answer = answer
            return answer

        # Answer course-specific follow-ups using the previous results.
        answer = self._course_question(s, msg)
        if answer:
            s.last_answer = answer
            return answer

        before = (
            tuple(s.interest),
            s.level,
            s.fmt,
            s.budget,
        )
        self._update_slots(s, msg)

        faq = self.kb.faq(msg) if not first or "?" in msg else None
        if faq and self._has(
            msg,
            "installments certificate recorded تقسيط شهادة مسجلة تسجيل pay",
        ):
            answer = faq["a_ar"] if s.lang == "ar" else faq["a_en"]
            s.last_answer = answer
            return answer

        if self._has(msg, "admission register enroll قبول تسجيل التقديم"):
            key = "requirements_ar" if s.lang == "ar" else "requirements_en"
            answer = self.kb.admission[key]
            s.last_answer = answer
            return answer

        if s.last_courses and before == (
            tuple(s.interest),
            s.level,
            s.fmt,
            s.budget,
        ):
            answer = self._t("help", s)
            s.last_answer = answer
            return answer

        if not s.interest:
            answer = self._t("greet" if first else "ask_interest", s)
        elif not s.level:
            answer = self._t("ask_level", s)
        elif not s.fmt and not s.budget and not s.last_courses:
            answer = self._t("ask_format", s)
        else:
            answer = self._recommend(s)

        s.last_answer = answer
        return answer
