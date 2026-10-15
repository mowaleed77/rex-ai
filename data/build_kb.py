"""Generates the SAMPLE knowledge base JSON files.
Replace the content with the academy's real, approved data (keep the same fields)."""
import json, pathlib
D = pathlib.Path(__file__).parent
SRC = "SAMPLE DATA - replace with academy-approved catalog"
UPD = "2026-10-14"

instructors = [
 {"id":"i1","name":"Dr. Mona Hassan","title_ar":"د. منى حسن","experience_years":12,"bio":"PhD in Computer Science; leads applied ML projects for banks and telecoms in Cairo.","specialties":["machine learning","python","data"]},
 {"id":"i2","name":"Eng. Ahmed Fathy","title_ar":"م. أحمد فتحي","experience_years":9,"bio":"Full-stack engineer and trainer; built production web platforms in Egypt and KSA.","specialties":["web","react","javascript"]},
 {"id":"i3","name":"Eng. Sara Nabil","title_ar":"م. سارة نبيل","experience_years":8,"bio":"Certified security analyst (CEH) with SOC experience.","specialties":["security","networks"]},
 {"id":"i4","name":"Ms. Laila Mansour","title_ar":"أ. ليلى منصور","experience_years":10,"bio":"Digital marketing consultant; managed regional ad campaigns.","specialties":["marketing","social media","seo"]},
 {"id":"i5","name":"Dr. Khaled Ibrahim","title_ar":"د. خالد إبراهيم","experience_years":15,"bio":"PMP-certified project director and business trainer.","specialties":["project management","business","excel"]},
 {"id":"i6","name":"Dr. Nour Adel","title_ar":"د. نور عادل","experience_years":11,"bio":"Health-informatics specialist working with hospital IT teams.","specialties":["healthcare","informatics","data"]},
]

def c(id,en,ar,dept,level,industry,hours,fmt,price,promo,prereq,aud,outcomes,desc,inst,careers,framework,kw):
    return dict(id=id,title_en=en,title_ar=ar,department=dept,level=level,industry=industry,
      duration_hours=hours,formats=fmt,price_egp=price,promotion=promo,prerequisites=prereq,
      target_audience=aud,learning_outcomes=outcomes,description=desc,instructor_id=inst,
      career_opportunities=careers,accreditation_framework=framework,country="Egypt",
      keywords=kw,data_source=SRC,updated=UPD)

courses = [
 c("C01","Python for Data Analysis","بايثون لتحليل البيانات","AI & Data","Beginner","Technology",40,["online","onsite"],4500,"15% off for early registration","None","Graduates and career switchers who want to start in data",
   ["Write Python scripts","Clean data with pandas","Build charts and dashboards","Present data insights"],
   "Hands-on introduction to Python, pandas and visualization for real datasets.","i1",["Data Analyst","BI Analyst"],"None claimed",
   "python data analysis analytics pandas visualization excel بايثون بيانات تحليل تحليل البيانات داتا"),
 c("C02","Machine Learning Fundamentals","أساسيات تعلم الآلة","AI & Data","Intermediate","Technology",48,["online","onsite","hybrid"],6500,"None","Python basics and school-level statistics","Analysts and developers moving into AI",
   ["Train and evaluate ML models","Apply feature engineering","Use scikit-learn","Deploy a simple model"],
   "Supervised and unsupervised learning with a capstone ML project.","i1",["ML Engineer","Data Scientist"],"None claimed",
   "machine learning ml ai artificial intelligence models scikit data science تعلم الآلة ذكاء اصطناعي الذكاء الاصطناعي"),
 c("C03","Generative AI & LLM Applications","تطبيقات الذكاء الاصطناعي التوليدي","AI & Data","Advanced","Technology",36,["online"],7500,"Group discount: 3+ seats 10%","Python and basic ML knowledge","Developers and technical leads",
   ["Design prompts and RAG pipelines","Build LLM agents","Evaluate and monitor LLM apps","Ship an AI assistant"],
   "Build retrieval-augmented assistants and multi-agent workflows with modern LLM APIs.","i1",["AI Engineer","LLM Application Developer"],"None claimed",
   "generative ai llm rag agents chatbot prompt openai gpt ذكاء اصطناعي توليدي شات بوت وكلاء"),
 c("C04","Web Development with React","تطوير الويب باستخدام React","Software","Beginner","Technology",60,["online","onsite"],5200,"None","Basic computer skills","Beginners who want to become web developers",
   ["Build responsive pages with HTML/CSS/JS","Create React apps","Consume REST APIs","Deploy a portfolio project"],
   "From HTML to a deployed React application with Git workflow.","i2",["Front-End Developer","Web Developer"],"None claimed",
   "web development react javascript html css frontend programming برمجة تطوير مواقع ويب جافاسكريبت"),
 c("C05","Cybersecurity Essentials","أساسيات الأمن السيبراني","Software","Beginner","Technology",32,["online","onsite"],4800,"10% off for students","Basic networking awareness","IT staff and graduates entering security",
   ["Identify common threats","Harden systems and networks","Run basic vulnerability scans","Respond to incidents"],
   "Core security concepts, tools and incident-response basics.","i3",["SOC Analyst","Security Associate"],"Aligned with common entry-level security competencies (not officially accredited)",
   "cybersecurity security hacking network protection soc أمن سيبراني امن المعلومات حماية شبكات"),
 c("C06","Digital Marketing Fundamentals","أساسيات التسويق الرقمي","Business","Beginner","Marketing",30,["online","onsite","hybrid"],3800,"WhatsApp registration bonus workshop","None","Entrepreneurs, graduates and marketing juniors",
   ["Plan multi-channel campaigns","Write effective ad copy","Use SEO and analytics","Measure campaign ROI"],
   "Practical social media, SEO and paid ads training with live campaigns.","i4",["Digital Marketer","Social Media Specialist"],"None claimed",
   "marketing digital social media ads seo facebook instagram تسويق رقمي اعلانات سوشيال ميديا"),
 c("C07","Project Management Professional Prep","التحضير لاحتراف إدارة المشاريع","Business","Intermediate","Management",35,["online","onsite"],6000,"None","2+ years of work experience","Team leads and aspiring project managers",
   ["Plan scope, time and cost","Manage risk and stakeholders","Apply agile and predictive methods","Prepare for PMP-style exams"],
   "Exam-oriented project management course with case studies.","i5",["Project Manager","PMO Analyst"],"Prepares for PMI-style exams (not an official PMI course)",
   "project management pmp agile scrum planning risk إدارة مشاريع ادارة المشروعات"),
 c("C08","Excel for Business Analysis","إكسل لتحليل الأعمال","Business","Beginner","Management",24,["online","onsite"],2800,"20% off this month","None","Office employees and accountants",
   ["Use formulas and lookups","Build pivot tables","Create dashboards","Automate reports"],
   "Practical Excel skills for reporting and analysis.","i5",["Business Analyst","Financial Assistant"],"None claimed",
   "excel spreadsheets pivot formulas reporting accounting اكسل جداول محاسبة تقارير"),
 c("C09","Healthcare Informatics Basics","أساسيات المعلوماتية الصحية","Healthcare","Beginner","Healthcare",28,["onsite","hybrid"],5000,"None","None","Healthcare staff and IT teams in hospitals",
   ["Understand EHR systems","Apply health data standards","Protect patient privacy","Analyze clinical data"],
   "Introduction to health IT systems, data standards and privacy.","i6",["Health Informatics Assistant","Clinical Data Coordinator"],"None claimed",
   "healthcare health informatics hospital medical ehr رعاية صحية معلوماتية صحية مستشفى طب"),
]

faqs = [
 {"id":"f1","q_en":"Can I pay in installments?","a_en":"Installment plans are available for courses above 4,000 EGP. Contact admissions to arrange one.","q_ar":"هل يمكن الدفع بالتقسيط؟","a_ar":"التقسيط متاح للدورات التي يزيد سعرها عن 4000 جنيه. تواصل مع قسم القبول.","keywords":"installments pay payment تقسيط دفع"},
 {"id":"f2","q_en":"Do I get a certificate?","a_en":"Yes, an academy completion certificate is issued after passing the final assessment. It is not an official accreditation unless stated on the course.","q_ar":"هل أحصل على شهادة؟","a_ar":"نعم، تصدر شهادة إتمام من الأكاديمية بعد اجتياز التقييم النهائي، وهي ليست اعتماداً رسمياً ما لم يُذكر ذلك في الدورة.","keywords":"certificate شهادة"},
 {"id":"f3","q_en":"Are sessions recorded?","a_en":"Online sessions are recorded and available for 30 days.","q_ar":"هل الجلسات مسجلة؟","a_ar":"الجلسات الأونلاين مسجلة ومتاحة لمدة 30 يوماً.","keywords":"recorded recording sessions تسجيل مسجلة"},
]
adm = {"requirements_en":"No entrance exam. Provide ID copy and, for intermediate/advanced courses, a short skills self-assessment.","requirements_ar":"لا يوجد اختبار قبول. يلزم صورة الهوية وتقييم ذاتي قصير للمستويات المتوسطة والمتقدمة.","data_source":SRC,"updated":UPD}

for name,obj in [("courses",courses),("instructors",instructors),("faqs",faqs),("admission",adm)]:
    (D/f"{name}.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
print("KB written")
