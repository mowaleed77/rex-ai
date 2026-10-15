"""REX Assistant conversation engine (Sprint 1 baseline).

Flow: collect interest/level/format/budget -> recommend with reasons -> answer
questions from the KB -> ask consent -> capture lead.
LLM wording/RAG upgrades are planned for Sprint 2; this baseline is deterministic and
grounded in data/*.json so it can be tested."""
import csv, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from .kb import KnowledgeBase, DATA_DIR
from .text import is_arabic, normalize, tokens

LEADS_FILE = DATA_DIR / "leads.csv"

LEVEL_AR = {"Beginner": "مبتدئ", "Intermediate": "متوسط", "Advanced": "متقدم"}
LEVELS = {"Beginner": "beginner none no experience zero start مبتدي مبتدئ جديد", "Intermediate": "intermediate some medium متوسط", "Advanced": "advanced expert professional متقدم محترف"}
FORMATS = {"online": "online remote اونلاين اون لاين عن بعد", "onsite": "onsite on-site offline in-person person حضوري", "hybrid": "hybrid مدمج"}
YES = set("yes y ok okay sure yep نعم ايوه اي اه موافق تمام اكيد".split())
NO = set("no n nope لا مش".split())

T = {  # bilingual message templates
 "greet": ("Hello! I'm REX, the academy's course assistant. Tell me about your background and what you'd like to learn or achieve.",
           "أهلاً! أنا REX مساعد الأكاديمية لاختيار الدورات. احكيلي عن خلفيتك وإيه اللي حابب تتعلمه أو توصل له."),
 "ask_interest": ("What topic or career path are you interested in (e.g. data, AI, web, security, marketing)?", "إيه المجال أو المسار الوظيفي اللي مهتم بيه (مثلاً بيانات، ذكاء اصطناعي، ويب، أمن سيبراني، تسويق)؟"),
 "ask_level": ("What's your current level: beginner, intermediate or advanced?", "مستواك الحالي إيه: مبتدئ، متوسط ولا متقدم؟"),
 "ask_format": ("Do you prefer online or on-site training? And do you have a budget in EGP?", "تفضل التدريب أونلاين ولا حضوري؟ وعندك ميزانية معينة بالجنيه؟"),
 "none": ("I couldn't find a matching course in our catalog. Our departments are: AI & Data, Software, Business, Healthcare. Could you rephrase your interest?", "ملقيتش دورة مناسبة في الكتالوج. أقسامنا: الذكاء الاصطناعي والبيانات، البرمجيات، الأعمال، الرعاية الصحية. ممكن توضح اهتمامك أكتر؟"),
 "consent": ("Would you like our admissions team to follow up with you? (yes/no) — we'll only save your details with your consent.", "تحب فريق القبول يتواصل معاك؟ (نعم/لا) — مش هنحفظ بياناتك غير بموافقتك."),
 "ask_name": ("Great, what's your name?", "تمام، اسمك إيه؟"),
 "ask_contact": ("Thanks! What's the best phone number or email to reach you?", "شكراً! رقم الهاتف أو الإيميل المناسب للتواصل؟"),
 "saved": ("Done — your details were saved for follow-up. Anything else I can help with?", "تم — حفظنا بياناتك للمتابعة. أي حاجة تانية أقدر أساعدك فيها؟"),
 "declined": ("No problem, nothing was saved. Ask me anything about the courses.", "ولا يهمك، مفيش حاجة اتحفظت. اسألني عن أي دورة."),
 "help": ("Ask me about the price, instructor, prerequisites or content of any recommended course — or tell me a new topic you'd like to explore.", "اسألني عن السعر أو المدرب أو المتطلبات أو المحتوى لأي دورة، أو قولي مجال جديد تحب تستكشفه."),
 "need_course": ("Which course do you mean? Tell me its name or ask me for a recommendation first.", "تقصد أنهي دورة؟ اذكر اسمها أو اطلب مني ترشيح الأول."),
}

@dataclass
class Session:
    lang: str = "en"
    interest: list[str] = field(default_factory=list)
    level: str | None = None
    fmt: str | None = None
    budget: int | None = None
    last_courses: list[dict] = field(default_factory=list)
    stage: str = "chat"   # chat | consent | name | contact
    lead: dict = field(default_factory=dict)
    started: bool = False

class RexAssistant:
    def __init__(self, kb: KnowledgeBase | None = None, leads_file: Path = LEADS_FILE):
        self.kb, self.leads_file = kb or KnowledgeBase(), leads_file

    # ---- helpers
    def _t(self, key, s): return T[key][1 if s.lang == "ar" else 0]
    @staticmethod
    def _has(text, vocab): 
        return bool(set(re.findall(r"\w+", normalize(text))) & set(re.findall(r"\w+", normalize(vocab))))

    def _update_slots(self, s: Session, msg: str):
        for lvl, vocab in LEVELS.items():
            if self._has(msg, vocab): s.level = lvl; break
        for fmt, vocab in FORMATS.items():
            if self._has(msg, vocab): s.fmt = fmt; break
        m = re.search(r"(\d[\d,]{2,})\s*(egp|le|جنيه|ج)?", msg.lower())
        if m: s.budget = int(m.group(1).replace(",", ""))
        slot_vocab = " ".join(list(LEVELS.values()) + list(FORMATS.values()))
        new = [t for t in tokens(msg) if t not in set(tokens(slot_vocab)) and not t.isdigit()]
        if s.last_courses and new and self.kb.search(" ".join(new)):
            s.interest, s.last_courses = [], []      # new topic: start a fresh recommendation
        s.interest += new

    # ---- intents
    def _course_question(self, s: Session, msg: str):
        n = normalize(msg); c = self.kb.find_course(msg) or (s.last_courses[0] if s.last_courses else None)
        asks = {
          "price": "price cost fee fees much offer offers promotion discount سعر تكلفه رسوم عرض خصم بكام",
          "duration": "duration hours long مده ساعات format formats",
          "instructor": "instructor trainer teacher teaches teach مدرب محاضر",
          "prereq": "prerequisite prerequisites requirements متطلبات شروط",
          "outcomes": "outcomes content syllabus topics محتوي مخرجات هتعلم",
          "audience": "audience career careers jobs وظايف فرص",
        }
        kind = next((k for k, v in asks.items() if self._has(n, v)), None)
        if not kind: return None
        if kind == "prereq" and "admission" in n: kind = None
        if not c: return self._t("need_course", s) if self.kb.find_course(msg) is None and not s.interest else None
        ar = s.lang == "ar"; name = c["title_ar"] if ar else c["title_en"]
        if kind == "price":
            promo = c["promotion"]; base = f"{name}: {c['price_egp']:,} EGP" if not ar else f"{name}: {c['price_egp']:,} جنيه"
            return base + (f" — {promo}" if promo != "None" else "") 
        if kind == "duration": return f"{name}: {c['duration_hours']} " + ("ساعة" if ar else "hours") + ", " + ", ".join(c["formats"])
        if kind == "instructor":
            i = self.kb.instructors[c["instructor_id"]]
            return f"{name}: {i['title_ar'] if ar else i['name']} — {i['experience_years']} " + ("سنة خبرة. " if ar else "years of experience. ") + i["bio"]
        if kind == "prereq": return f"{name}: " + c["prerequisites"]
        if kind == "outcomes": return f"{name}: " + "; ".join(c["learning_outcomes"])
        return f"{name}: " + c["target_audience"] + " | " + ", ".join(c["career_opportunities"])

    def _recommend(self, s: Session):
        hits = self.kb.search(" ".join(s.interest), top_k=8)
        ranked = []
        for score, c in hits:
            order = ["Beginner", "Intermediate", "Advanced"]
            gap = order.index(c["level"]) - order.index(s.level) if s.level else 0
            bonus = 2 if gap == 0 else (-3 * gap if gap > 0 else -1)   # penalise courses above the user's level
            if s.fmt and s.fmt not in c["formats"]: bonus -= 3
            if s.budget and c["price_egp"] > s.budget: bonus -= 3
            ranked.append((score + bonus, c))
        ranked.sort(key=lambda x: -x[0])
        top = ranked[0][0] if ranked else 0
        ranked = [c for sc, c in ranked if sc >= 0.4 * top][:3]
        s.last_courses = ranked
        if not ranked: return self._t("none", s)
        ar = s.lang == "ar"
        order = ["Beginner", "Intermediate", "Advanced"]
        lvl = lambda c: order.index(c["level"]) - (order.index(s.level) if s.level else 0)
        if s.level and not any(lvl(c) <= 0 for c in ranked):
            lines = [f"مفيش دورة في المجال ده لمستوى {LEVEL_AR[s.level]} حالياً. دي أقرب الدورات (مستواها أعلى):" if ar
                     else f"We don't have a {s.level} course on this topic yet. These are the closest options (above your level):"]
        else:
            lines = ["أنسب الدورات ليك:" if ar else "Here are the best matches for you:"]
        for n, c in enumerate(ranked, 1):
            why = []
            if s.level == c["level"]: why.append("مستواها " + LEVEL_AR[c["level"]] if ar else f"it's a {c['level']} course matching your level")
            if s.fmt and s.fmt in c["formats"]: why.append("متاحة " + {"online":"أونلاين","onsite":"حضوري","hybrid":"مدمج"}[s.fmt] if ar else f"available {s.fmt}")
            if s.budget and c["price_egp"] <= s.budget: why.append("ضمن ميزانيتك" if ar else "within your budget")
            why.append(c["description"])
            if lvl(c) > 0:
                why.append(("ملحوظة: مستواها أعلى من مستواك، والمتطلبات: " if ar else "Note: above your level — prerequisites: ") + c["prerequisites"])
            title = c["title_ar"] if ar else c["title_en"]
            price = f"{c['price_egp']:,} " + ("جنيه" if ar else "EGP")
            if ar: meta = f"{LEVEL_AR[c['level']]}، {c['duration_hours']} ساعة، {price}"
            else: meta = f"{c['level']}, {c['duration_hours']}h, {price}"
            lines.append(f"{n}. {title} ({meta})\n   " + ("السبب: " if ar else "Why: ") + "; ".join(why))
        lines.append("")
        lines.append("تقدر تسألني عن السعر أو المدرب أو المتطلبات لأي دورة." if ar else "Ask me about price, instructor, prerequisites or content of any of them.")
        s.stage = "consent"
        lines.append(self._t("consent", s))
        return "\n".join(lines)

    def _save_lead(self, s: Session):
        new = not self.leads_file.exists()
        with open(self.leads_file, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new: w.writerow(["timestamp", "name", "contact", "interest", "level", "format", "budget", "recommended", "consent"])
            w.writerow([datetime.now(timezone.utc).isoformat(), s.lead.get("name"), s.lead.get("contact"), " ".join(dict.fromkeys(s.interest)), s.level, s.fmt, s.budget, "|".join(c["id"] for c in s.last_courses), "yes"])

    # ---- main entry
    def reply(self, s: Session, msg: str) -> str:
        msg = msg.strip()
        if not msg: return self._t("greet", s)
        s.lang = "ar" if is_arabic(msg) else "en"
        words = set(re.findall(r"\w+", normalize(msg)))

        if s.stage == "consent" and len(words) <= 2:      # short yes/no answer to the consent offer
            if words & {normalize(w) for w in YES}: s.stage = "name"; return self._t("ask_name", s)
            if words & {normalize(w) for w in NO}: s.stage = "chat"; return self._t("declined", s)
        elif s.stage == "name":
            s.lead["name"] = msg; s.stage = "contact"; return self._t("ask_contact", s)
        elif s.stage == "contact":
            s.lead["contact"] = msg; s.stage = "chat"; self._save_lead(s); return self._t("saved", s)

        first = not s.started; s.started = True
        ans = self._course_question(s, msg)      # questions never change the user's topic
        if ans: return ans
        before = (tuple(s.interest), s.level, s.fmt, s.budget)
        self._update_slots(s, msg)
        faq = self.kb.faq(msg) if not first or "?" in msg else None
        if faq and not s.interest[:0] and (self._has(msg, "installments certificate recorded تقسيط شهادة مسجلة تسجيل pay")):
            return faq["a_ar"] if s.lang == "ar" else faq["a_en"]
        if self._has(msg, "admission register enroll قبول تسجيل التقديم"):
            return self.kb.admission["requirements_ar" if s.lang == "ar" else "requirements_en"]
        if s.last_courses and before == (tuple(s.interest), s.level, s.fmt, s.budget): return self._t("help", s)
        if not s.interest: return self._t("greet" if first else "ask_interest", s)
        if not s.level: return self._t("ask_level", s)
        if not s.fmt and not s.budget and not s.last_courses: return self._t("ask_format", s)
        return self._recommend(s)
