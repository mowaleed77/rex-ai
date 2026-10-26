"""Builds the RAG document corpus (data/rag_docs/*.md) from the structured knowledge base.

Run after editing data/*.json:   python -m rex.rag.build_docs
Every document starts with a small metadata header (type, language, source, update date) so
answers stay traceable. No facts are invented here: everything comes from the JSON files."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "rag_docs"

DEPT_AR = {"AI & Data": "الذكاء الاصطناعي والبيانات", "Software": "البرمجيات", "Business": "الأعمال", "Healthcare": "الرعاية الصحية"}
LEVEL_AR = {"Beginner": "مبتدئ", "Intermediate": "متوسط", "Advanced": "متقدم"}
FORMAT_AR = {"online": "أونلاين", "onsite": "حضوري", "hybrid": "مدمج"}


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def header(doc_id, dtype, lang, title, keywords, source, updated, **extra):
    meta = {"doc_id": doc_id, "type": dtype, "language": lang, "title": title, "keywords": keywords,
            "source": source, "updated": updated, **extra}
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n---\n"


def write(doc_id, text):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{doc_id}.md").write_text(text, encoding="utf-8")


def main():
    courses, instructors = load("courses"), {i["id"]: i for i in load("instructors")}
    faqs, adm = load("faqs"), load("admission")
    src, upd = courses[0]["data_source"], courses[0]["updated"]
    for old in OUT.glob("*.md") if OUT.exists() else []:
        old.unlink()  # rebuild from scratch so removed courses disappear

    # ---- one document per course (EN + AR)
    for c in courses:
        i = instructors[c["instructor_id"]]
        fmts_en = ", ".join(c["formats"]); fmts_ar = "، ".join(FORMAT_AR[f] for f in c["formats"])
        write(f"course_{c['id']}_en", header(f"course_{c['id']}_en", "course", "en", c["title_en"], c["keywords"], c["data_source"], c["updated"], course_id=c["id"]) + f"""
# {c['title_en']} (Course {c['id']})
- Department: {c['department']}
- Level: {c['level']}
- Industry: {c['industry']}
- Duration: {c['duration_hours']} hours
- Training formats: {fmts_en}
- Price: {c['price_egp']:,} EGP
- Current offer: {c['promotion']}
- Prerequisites: {c['prerequisites']}
- Target audience: {c['target_audience']}
- Instructor: {i['name']} ({i['experience_years']} years of experience)
- Career opportunities: {', '.join(c['career_opportunities'])}
- Accreditation: {c['accreditation_framework']}

## Description
{c['description']}

## Learning outcomes
""" + "\n".join(f"- {o}" for o in c["learning_outcomes"]) + "\n")
        write(f"course_{c['id']}_ar", header(f"course_{c['id']}_ar", "course", "ar", c["title_ar"], c["keywords"], c["data_source"], c["updated"], course_id=c["id"]) + f"""
# {c['title_ar']} (الدورة {c['id']})
- القسم: {DEPT_AR.get(c['department'], c['department'])}
- المستوى: {LEVEL_AR[c['level']]}
- المدة: {c['duration_hours']} ساعة
- صيغ التدريب: {fmts_ar}
- السعر: {c['price_egp']:,} جنيه مصري
- العرض الحالي: {c['promotion_ar']}
- المتطلبات: {c['prerequisites_ar']}
- الفئة المستهدفة: {c['target_audience_ar']}
- المدرب: {i['title_ar']} ({i['experience_years']} سنة خبرة)
- فرص العمل: {'، '.join(c['career_opportunities_ar'])}
- الاعتماد: {c['accreditation_framework_ar']}

## الوصف
{c['description_ar']}

## مخرجات التعلم
""" + "\n".join(f"- {o}" for o in c["learning_outcomes_ar"]) + "\n")

    # ---- course catalog overview
    write("catalog_en", header("catalog_en", "catalog", "en", "Course catalog (all courses)", "catalog all courses list available which courses what do you offer departments", src, upd) + "\n# Course catalog\n" +
          "\n".join(f"- {c['title_en']} (Course {c['id']}) — {c['department']}, {c['level']}, {c['duration_hours']} hours, {c['price_egp']:,} EGP" for c in courses) + "\n")
    write("catalog_ar", header("catalog_ar", "catalog", "ar", "كتالوج الدورات (كل الدورات)", "كتالوج كل الدورات قائمة المتاحة ايه الدورات اللي عندكم الاقسام", src, upd) + "\n# كتالوج الدورات\n" +
          "\n".join(f"- {c['title_ar']} (الدورة {c['id']}) — {DEPT_AR.get(c['department'], c['department'])}، {LEVEL_AR[c['level']]}، {c['duration_hours']} ساعة، {c['price_egp']:,} جنيه" for c in courses) + "\n")

    # ---- pricing and promotions
    write("pricing_en", header("pricing_en", "pricing", "en", "Pricing and promotions", "price prices cost fee fees offers promotions discount installments cheapest budget", src, upd) + "\n# Pricing and promotions (EGP)\n" +
          "\n".join(f"- {c['title_en']}: {c['price_egp']:,} EGP — offer: {c['promotion']}" for c in courses) + "\n")
    write("pricing_ar", header("pricing_ar", "pricing", "ar", "الأسعار والعروض", "سعر اسعار تكلفة رسوم عروض خصم تقسيط ميزانية الارخص بكام كام", src, upd) + "\n# الأسعار والعروض (جنيه مصري)\n" +
          "\n".join(f"- {c['title_ar']}: {c['price_egp']:,} جنيه — العرض: {c['promotion_ar']}" for c in courses) + "\n")

    # ---- schedules and training formats (no dates in the data: do not invent any)
    write("formats_en", header("formats_en", "formats", "en", "Schedules and training formats", "schedule schedules format formats online onsite hybrid duration hours start dates timing", src, upd) + "\n# Training formats and duration\n" +
          "\n".join(f"- {c['title_en']}: {c['duration_hours']} hours; formats: {', '.join(c['formats'])}" for c in courses) +
          "\n\nExact start dates and session times are not listed in this knowledge base; the learner should contact admissions for the current schedule.\n")
    write("formats_ar", header("formats_ar", "formats", "ar", "المواعيد وصيغ التدريب", "جدول مواعيد صيغة صيغ اونلاين حضوري مدمج مدة ساعات بداية توقيت", src, upd) + "\n# صيغ التدريب والمدة\n" +
          "\n".join(f"- {c['title_ar']}: {c['duration_hours']} ساعة؛ الصيغ: {'، '.join(FORMAT_AR[f] for f in c['formats'])}" for c in courses) +
          "\n\nمواعيد البدء وأوقات الجلسات غير مذكورة في قاعدة المعرفة الحالية؛ على المتعلم التواصل مع قسم القبول لمعرفة الجدول الحالي.\n")

    # ---- instructor profiles
    def teaches(i, key): return [c[key] for c in courses if c["instructor_id"] == i["id"]]
    write("instructors_en", header("instructors_en", "instructors", "en", "Instructor profiles", "instructor instructors trainer teacher profile experience who teaches", src, upd) + "\n# Instructor profiles\n" +
          "\n".join(f"\n## {i['name']}\n- Experience: {i['experience_years']} years\n- Courses: {', '.join(teaches(i, 'title_en'))}\n- Profile: {i['bio']}" for i in instructors.values()) + "\n")
    write("instructors_ar", header("instructors_ar", "instructors", "ar", "ملفات المدربين", "مدرب مدربين محاضر ملف خبرة مين بيدرس", src, upd) + "\n# ملفات المدربين\n" +
          "\n".join(f"\n## {i['title_ar']}\n- الخبرة: {i['experience_years']} سنة\n- الدورات: {'، '.join(teaches(i, 'title_ar'))}\n- نبذة: {i['bio_ar']}" for i in instructors.values()) + "\n")

    # ---- FAQ
    write("faq_en", header("faq_en", "faq", "en", "Frequently asked questions", "faq questions installments certificate recorded sessions", src, upd) + "\n# FAQ\n" +
          "\n".join(f"\n**Q: {f['q_en']}**\nA: {f['a_en']}" for f in faqs) + "\n")
    write("faq_ar", header("faq_ar", "faq", "ar", "الأسئلة الشائعة", "اسئلة شائعة تقسيط شهادة تسجيل الجلسات", src, upd) + "\n# الأسئلة الشائعة\n" +
          "\n".join(f"\n**س: {f['q_ar']}**\nج: {f['a_ar']}" for f in faqs) + "\n")

    # ---- admission
    write("admission_en", header("admission_en", "admission", "en", "Admission requirements", "admission requirements register registration enroll apply documents entrance exam", adm["data_source"], adm["updated"]) + f"\n# Admission requirements\n{adm['requirements_en']}\n")
    write("admission_ar", header("admission_ar", "admission", "ar", "شروط القبول", "قبول شروط تسجيل تقديم التقديم اوراق مستندات اختبار", adm["data_source"], adm["updated"]) + f"\n# شروط القبول\n{adm['requirements_ar']}\n")

    print(f"Wrote {len(list(OUT.glob('*.md')))} documents to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
