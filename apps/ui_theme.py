"""Look and feel for the REX AI app: CSS, small HTML helpers and the English / Arabic UI texts."""
from __future__ import annotations

from html import escape

NAVY = "#1F3A5F"
TEAL = "#0F766E"
ACCENT = "#2563EB"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Cairo:wght@400;600;700&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', 'Cairo', 'Segoe UI', Tahoma, sans-serif; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1180px; }

/* hero banner */
.rex-hero { background: linear-gradient(120deg, #1F3A5F 0%, #2563EB 100%); color: #fff; border-radius: 16px;
  padding: 22px 28px; margin-bottom: 18px; display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 6px 20px rgba(31,58,95,.18); }
.rex-hero h1 { margin: 0; font-size: 1.7rem; font-weight: 700; color: #fff; letter-spacing: -.01em; }
.rex-hero p { margin: 4px 0 0 0; opacity: .88; font-size: .95rem; }
.rex-badge { background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35); border-radius: 999px;
  padding: 4px 14px; font-size: .8rem; white-space: nowrap; }

/* cards and pills */
.rex-card { background: var(--background-color, #fff); border: 1px solid rgba(120,130,150,.28); border-radius: 14px;
  padding: 16px 18px; margin: 8px 0; }
.rex-card h4 { margin: 0 0 6px 0; font-size: 1rem; }
.rex-muted { color: #6b7280; font-size: .85rem; }
.rex-pill { display: inline-block; border-radius: 999px; padding: 2px 11px; font-size: .78rem; font-weight: 600; }
.rex-pill.ok { background: #DCFCE7; color: #166534; }
.rex-pill.warn { background: #FEF3C7; color: #92400E; }
.rex-pill.bad { background: #FEE2E2; color: #991B1B; }
.rex-pill.info { background: #DBEAFE; color: #1E40AF; }
.rex-pill.muted { background: #E5E7EB; color: #374151; }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid rgba(120,130,150,.25); flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 8px 16px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: rgba(37,99,235,.10); color: #1D4ED8; }

/* buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button { border-radius: 10px; font-weight: 600; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background: #2563EB; border: 0; }

/* chat */
.stChatMessage { border-radius: 14px; padding: 10px 14px; }
.stChatMessage p, .stChatMessage li { unicode-bidi: plaintext; text-align: start; line-height: 1.65; }
[data-testid="stChatInput"] textarea { unicode-bidi: plaintext; }

/* login */
.rex-login { max-width: 440px; margin: 2.5rem auto 0 auto; }
.rex-login .rex-hero { flex-direction: column; text-align: center; }

/* sidebar */
section[data-testid="stSidebar"] { background: #F4F6FA; }
.rex-user { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.rex-brand { display: flex; align-items: center; gap: 10px; margin: 2px 0 14px 0; }
.rex-brand small { color: #6b7280; }
.rex-logo { width: 44px; height: 44px; border-radius: 12px; overflow: hidden; flex: none;
  box-shadow: 0 2px 8px rgba(31,58,95,.25); }
.rex-logo svg, .rex-avatar svg { width: 100%; height: 100%; display: block; }
.rex-nav-title { text-transform: uppercase; letter-spacing: .08em; font-size: .68rem; font-weight: 700;
  color: #6b7280; margin: 16px 4px 6px 4px; }
section[data-testid="stSidebar"] .stButton > button > div,
section[data-testid="stSidebar"] .stButton > button [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] .stButton > button p { justify-content: flex-start !important; text-align: start !important;
  width: 100%; margin: 0; }
section[data-testid="stSidebar"] .stButton > button { justify-content: flex-start; text-align: start; border: 0;
  background: transparent; color: inherit; padding: 8px 12px; border-radius: 10px; font-weight: 500; }
section[data-testid="stSidebar"] .stButton > button:hover { background: rgba(37,99,235,.10); }
section[data-testid="stSidebar"] .stButton > button[kind="primary"] { background: #2563EB; color: #fff; font-weight: 600; }
.rex-timeline { border-inline-start: 2px solid rgba(120,130,150,.35); margin: 6px 10px; padding-inline-start: 16px; }
.rex-tl-row { position: relative; margin: 0 0 14px 0; }
.rex-tl-dot { position: absolute; inset-inline-start: -29px; top: 1px; width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-size: .75rem; font-weight: 700; color: #fff; }
.rex-tl-row.ok .rex-tl-dot { background: #16A34A; } .rex-tl-row.bad .rex-tl-dot { background: #DC2626; }
.rex-tl-msg { font-size: .88rem; }
.rex-flow { background: rgba(37,99,235,.08); border-radius: 10px; padding: 8px 14px; margin: 6px 0 10px 0; font-weight: 600; }
.rex-avatar { width: 46px; height: 46px; border-radius: 50%; background: #1F3A5F; color: #fff; display: flex;
  align-items: center; justify-content: center; font-weight: 700; overflow: hidden; flex: none;
  border: 2px solid #fff; box-shadow: 0 0 0 2px rgba(37,99,235,.35); }
.rex-pick { width: 84px; height: 84px; border-radius: 50%; overflow: hidden; margin: 0 auto 6px auto;
  border: 3px solid transparent; }
.rex-pick.sel { border-color: #2563EB; box-shadow: 0 0 0 3px rgba(37,99,235,.25); }
.rex-pick svg { width: 100%; height: 100%; display: block; }
</style>
"""

RTL_CSS = """
<style>
.stApp, .block-container { direction: rtl; }
.block-container, .stMarkdown, .stCaption, label, .stTextInput input, .stTextArea textarea,
.stSelectbox, .stMultiSelect, .rex-card, .rex-hero { text-align: right; }
.stTabs [data-baseweb="tab-list"] { flex-direction: row-reverse; justify-content: flex-end; }
section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] .stCaption { text-align: right; direction: rtl; }
section[data-testid="stSidebar"] .stButton > button { justify-content: flex-start; text-align: right; direction: rtl; }
</style>
"""


def inject(st, rtl: bool = False) -> None:
    st.markdown(CSS + (RTL_CSS if rtl else ""), unsafe_allow_html=True)


def hero(st, title: str, subtitle: str = "", badge: str = "") -> None:
    badge_html = f'<span class="rex-badge">{escape(badge)}</span>' if badge else ""
    st.markdown(
        f'<div class="rex-hero"><div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>{badge_html}</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------ greeting robot
ROBOT_CSS = """
<style>
.rex-greet { display: flex; align-items: center; gap: 18px; padding: 14px 22px; margin: 0 0 16px 0;
  border-radius: 18px; background: linear-gradient(120deg, #EFF6FF 0%, #F0FDFA 100%);
  border: 1px solid rgba(37,99,235,.25); box-shadow: 0 6px 20px rgba(31,58,95,.10); overflow: hidden;
  max-height: 220px; animation: rexGreetIn .6s ease both, rexGreetOut .7s ease 11s forwards; }
.rex-greet svg { width: 112px; height: 130px; flex: none; animation: rexBob 2.4s ease-in-out infinite; }
.rex-bubble { position: relative; background: #fff; border: 1px solid rgba(37,99,235,.25); border-radius: 16px;
  padding: 12px 18px; color: #1F3A5F; line-height: 1.6; box-shadow: 0 2px 8px rgba(31,58,95,.08); }
.rex-bubble b { font-size: 1.05rem; display: block; margin-bottom: 2px; }
.rex-bubble::before { content: ""; position: absolute; inset-inline-start: -9px; top: 26px; width: 16px; height: 16px;
  background: #fff; border-inline-start: 1px solid rgba(37,99,235,.25); border-bottom: 1px solid rgba(37,99,235,.25);
  transform: rotate(45deg); }
[dir="rtl"] .rex-bubble::before, .rex-greet.ar .rex-bubble::before { transform: rotate(-135deg); }
.rex-greet.ar { direction: rtl; text-align: right; }
.rex-wave { transform-origin: 92px 96px; animation: rexWave 1.1s ease-in-out 0.5s 4; }
.rex-eye { transform-box: fill-box; transform-origin: center; animation: rexBlink 4s infinite; }
.rex-ant { animation: rexPulse 1.2s ease-in-out infinite; }
@keyframes rexGreetIn { from { opacity: 0; transform: translateY(-14px); } to { opacity: 1; transform: none; } }
@keyframes rexGreetOut { to { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; margin-bottom: 0; border-width: 0; } }
@keyframes rexBob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
@keyframes rexWave { 0%, 100% { transform: rotate(0); } 25% { transform: rotate(-38deg); } 75% { transform: rotate(18deg); } }
@keyframes rexBlink { 0%, 92%, 100% { transform: scaleY(1); } 95% { transform: scaleY(.1); } }
@keyframes rexPulse { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
@media (prefers-reduced-motion: reduce) { .rex-greet, .rex-greet * { animation: none !important; } }
</style>
"""

ROBOT_SVG = (
    '<svg viewBox="0 0 120 140" role="img" aria-label="REX robot waving hello">'
    '<line x1="60" y1="10" x2="60" y2="26" stroke="#1F3A5F" stroke-width="3" stroke-linecap="round"/>'
    '<circle class="rex-ant" cx="60" cy="8" r="5" fill="#0F766E"/>'
    '<rect x="22" y="26" width="76" height="56" rx="18" fill="#2563EB"/>'
    '<rect x="30" y="34" width="60" height="40" rx="12" fill="#E0ECFF"/>'
    '<circle class="rex-eye" cx="47" cy="52" r="6" fill="#1F3A5F"/><circle class="rex-eye" cx="73" cy="52" r="6" fill="#1F3A5F"/>'
    '<circle cx="49" cy="50" r="1.8" fill="#fff"/><circle cx="75" cy="50" r="1.8" fill="#fff"/>'
    '<path d="M47 63 Q60 73 73 63" fill="none" stroke="#1F3A5F" stroke-width="3" stroke-linecap="round"/>'
    '<rect x="12" y="62" width="8" height="16" rx="4" fill="#1F3A5F"/><rect x="100" y="62" width="8" height="16" rx="4" fill="#1F3A5F"/>'
    '<rect x="34" y="86" width="52" height="40" rx="14" fill="#1F3A5F"/>'
    '<circle cx="60" cy="104" r="7" fill="#0F766E"/><circle cx="60" cy="104" r="3" fill="#99F6E4"/>'
    '<rect x="16" y="92" width="14" height="30" rx="7" fill="#2563EB"/>'
    '<g class="rex-wave"><rect x="90" y="70" width="14" height="30" rx="7" fill="#2563EB"/>'
    '<circle cx="97" cy="68" r="8" fill="#E0ECFF" stroke="#2563EB" stroke-width="2"/></g>'
    '</svg>'
)


def greeting_text(name: str, is_admin: bool, arabic: bool, hour: int, pending: int = 0) -> tuple[str, str]:
    """(headline, message) for the robot's speech bubble."""
    if arabic:
        hello = "صباح الخير" if 5 <= hour < 12 else "مساء الخير" if 12 <= hour < 22 else "أهلاً بك"
        head = f"{hello} يا {name}! 👋"
        if is_admin:
            body = "أنا REX، مساعدك الذكي. "
            body += (f"لديك {pending} حملة تسويقية بانتظار موافقتك." if pending
                     else "لا توجد حملات بانتظار الموافقة، ويمكنك مراجعة المناقصات أو إطلاق دورة جديدة.")
        else:
            body = "أنا REX. اسألني عن الدورات، أو ارفع سيرتك الذاتية وسأرشّح لك الأنسب."
    else:
        hello = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else \
            "Good evening" if 18 <= hour < 22 else "Welcome"
        head = f"{hello}, {name}! 👋"
        if is_admin:
            body = "I'm REX, your AI assistant. "
            body += (f"{pending} campaign(s) are waiting for your approval." if pending
                     else "No campaigns are waiting - review tenders or launch a new course.")
        else:
            body = "I'm REX. Ask me about courses, or upload your CV and I'll find your best match."
    return head, body


def robot_greeting(st, name: str, is_admin: bool = False, arabic: bool = False, hour: int = 12,
                   pending: int = 0) -> None:
    """Animated robot that waves and says hello. Shown once after each sign-in (fades out by itself)."""
    head, body = greeting_text(name, is_admin, arabic, hour, pending)
    html = (f'<div class="rex-greet{" ar" if arabic else ""}">{ROBOT_SVG}'
            f'<div class="rex-bubble"><b>{escape(head)}</b>{escape(body)}</div></div>')
    st.markdown(ROBOT_CSS + html, unsafe_allow_html=True)


def pill(text: str, kind: str = "info") -> str:
    return f'<span class="rex-pill {kind}">{escape(str(text))}</span>'


STATUS_KIND = {"draft": "muted", "in_review": "info", "changes_requested": "warn", "approved": "ok",
               "pending_admin_approval": "warn", "rejected": "bad"}

# -------------------------------------------------------------------- UI texts
TR = {
    "en": {
        "app_title": "REX AI - Smart Academy",
        "tagline": "Course advice, curriculum design, documents, marketing and tender research - one coordinated system.",
        "sign_in": "Sign in", "sign_up": "Create account", "username": "Username", "password": "Password",
        "full_name": "Full name", "email": "Email (optional)", "confirm": "Confirm password",
        "sign_out": "Sign out", "signed_in_as": "Signed in as",
        "welcome_back": "Welcome back", "bad_login": "Wrong username or password.",
        "account_created": "Account created. You are signed in.",
        "pw_mismatch": "The two passwords do not match.",
        "change_pw_title": "Choose a new password",
        "change_pw_info": "This account uses a temporary or default password. Set your own to continue.",
        "current_pw": "Current password", "new_pw": "New password", "save": "Save",
        "tab_assistant": "Assistant", "tab_command": "Command Center", "tab_curriculum": "Curriculum",
        "tab_documents": "Documents", "tab_marketing": "Marketing", "tab_rfp": "RFP Research",
        "tab_profile": "My Profile", "tab_admin": "Admin",
        "role_admin": "Admin", "role_user": "User",
        "brand_sub": "Smart Academy", "nav_overview": "Overview", "tab_dashboard": "Dashboard", "nav_agents": "Agents", "nav_account": "Account",
        "nav_admin": "Administration", "nav_settings": "Settings",
        "chat_placeholder": "Ask about courses, prices, duration, careers... (English or Arabic)",
        "chat_welcome": "Hi! I'm REX. Tell me what you want to learn and I'll recommend the right course.",
        "new_chat": "New conversation", "share_details": "Let admissions contact me",
        "share_help": "Sends your saved name and contact details to the admissions team (only with your consent).",
        "lead_saved": "Done - the admissions team will contact you.",
        "need_contact": "Add your phone or email in My Profile first.",
    },
    "ar": {
        "app_title": "REX AI - الأكاديمية الذكية",
        "tagline": "إرشاد الدورات، تصميم المناهج، المستندات، التسويق والبحث عن المناقصات - في نظام واحد متكامل.",
        "sign_in": "تسجيل الدخول", "sign_up": "إنشاء حساب", "username": "اسم المستخدم", "password": "كلمة المرور",
        "full_name": "الاسم الكامل", "email": "البريد الإلكتروني (اختياري)", "confirm": "تأكيد كلمة المرور",
        "sign_out": "تسجيل الخروج", "signed_in_as": "مسجّل الدخول باسم",
        "welcome_back": "مرحباً بعودتك", "bad_login": "اسم المستخدم أو كلمة المرور غير صحيحة.",
        "account_created": "تم إنشاء الحساب وتسجيل دخولك.",
        "pw_mismatch": "كلمتا المرور غير متطابقتين.",
        "change_pw_title": "اختر كلمة مرور جديدة",
        "change_pw_info": "هذا الحساب يستخدم كلمة مرور مؤقتة أو افتراضية. عيّن كلمة مرورك للمتابعة.",
        "current_pw": "كلمة المرور الحالية", "new_pw": "كلمة المرور الجديدة", "save": "حفظ",
        "tab_assistant": "المساعد", "tab_command": "مركز القيادة", "tab_curriculum": "المنهج",
        "tab_documents": "المستندات", "tab_marketing": "التسويق", "tab_rfp": "بحث المناقصات",
        "tab_profile": "ملفي الشخصي", "tab_admin": "الإدارة",
        "role_admin": "مدير", "role_user": "مستخدم",
        "brand_sub": "الأكاديمية الذكية", "nav_overview": "نظرة عامة", "tab_dashboard": "لوحة المتابعة", "nav_agents": "الوكلاء", "nav_account": "الحساب",
        "nav_admin": "الإدارة", "nav_settings": "الإعدادات",
        "chat_placeholder": "اسأل عن الدورات والأسعار والمدة وفرص العمل... (بالعربية أو الإنجليزية)",
        "chat_welcome": "أهلاً! أنا REX. أخبرني ماذا تريد أن تتعلم وسأرشّح لك الدورة المناسبة.",
        "new_chat": "محادثة جديدة", "share_details": "أريد أن يتواصل معي فريق القبول",
        "share_help": "يرسل اسمك وبيانات التواصل المحفوظة إلى فريق القبول (بموافقتك فقط).",
        "lead_saved": "تم - سيتواصل معك فريق القبول.",
        "need_contact": "أضف رقم هاتفك أو بريدك في ملفي الشخصي أولاً.",
    },
}
