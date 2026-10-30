from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .base import Agent, AgentResult

logger = logging.getLogger(__name__)


class DocumentAgent(Agent):
    name = "document"

    SUPPORTED = {"curriculum_report", "course_description", "gap_analysis"}

    def run(self, task: dict) -> AgentResult:
        doc_type = task.get("document_type")
        title = task.get("title", "REX Academy Report")
        content = task.get("content")
        meta = task.get("metadata") or {}
        output_dir = Path(task.get("output_dir", "generated_docs"))

        if doc_type not in self.SUPPORTED:
            return AgentResult(
                self.name,
                False,
                message=(
                    "Unsupported document_type. Choose: "
                    + ", ".join(sorted(self.SUPPORTED))
                ),
            )

        # --- SAFE DIRECT RAG CORPUS READING ---
        course_name = meta.get("Course", title)
        rag_context = ""
        try:
            root_dir = Path(__file__).resolve().parents[2]
            docs_dir = root_dir / "data" / "rag_docs"
            if docs_dir.exists():
                snippets = []
                for md_file in docs_dir.glob("*.md"):
                    text = md_file.read_text(encoding="utf-8", errors="ignore")
                    if course_name.lower() in text.lower():
                        snippets.append(text[:300])
                rag_context = " ".join(snippets)
        except Exception:
            pass
        # --------------------------------------

        if not isinstance(content, dict) or not content:
            content = self._auto_generate_content(doc_type, title, meta, rag_context)

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
            output_path = output_dir / f"{doc_type}_{safe_title}.pdf"

            styles = self._styles()
            story = []
            story += self._header(title, meta, styles)
            story += getattr(self, f"_build_{doc_type}")(content, styles)
            story += self._footer(styles)

            SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=2 * cm,
                rightMargin=2 * cm,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
                title=title,
            ).build(story)

            return AgentResult(
                self.name,
                True,
                output={
                    "document_type": doc_type,
                    "file_path": str(output_path.resolve()),
                },
                message=f"PDF created successfully: {output_path.resolve()}",
            )

        except Exception as error:
            logger.exception("DocumentAgent failed for type=%s", doc_type)
            return AgentResult(
                self.name, False, message=f"Could not generate PDF: {error}"
            )

    def _auto_generate_content(self, doc_type: str, title: str, meta: dict, rag_context: str) -> dict:
        course_name = meta.get("Course", title)
        audience = meta.get("Audience", "Professionals and Students")
        level = meta.get("Level", audience)
        base_overview = rag_context if rag_context else f"Comprehensive training program for {course_name}."

        if doc_type == "curriculum_report":
            return {
                "overview": f"{base_overview[:300]} Designed to take learners from core fundamentals to professional competency.",
                "objectives": [
                    f"Master the core principles of {course_name}",
                    "Apply theoretical concepts through supervised labs",
                    "Build and present a complete capstone project"
                ],
                "modules": [
                    {"title": "Module 1: Fundamentals", "topics": ["Introduction", "Environment Setup", "Core Syntax"], "hours": 6},
                    {"title": "Module 2: Practical Application", "topics": ["Data Handling", "Workflows", "Error Mitigation"], "hours": 10},
                    {"title": "Module 3: Advanced Topics", "topics": ["Optimization", "Best Practices", "Deployment"], "hours": 8}
                ],
                "assessments": ["Weekly quizzes", "Practical lab assessments", "Final capstone review"],
                "capstone": f"Develop a production-ready application showcasing {course_name} expertise."
            }
        elif doc_type == "course_description":
            return {
                "pitch": f"Accelerate your career with our certified {course_name} program. Tailored for {audience}.",
                "audience": audience,
                "level": level,
                "duration": "24 Hours (4 Weeks)",
                "format": "Hybrid / Online Interactive",
                "fee": "EGP 5,000",
                "prerequisites": "Basic foundational literacy",
                "outcomes": [
                    f"Professional fluency in {course_name}",
                    "Complete real-world projects for your portfolio",
                    "Direct feedback from certified academy instructors"
                ],
                "careers": ["Specialist", "Consultant", "Technical Lead"]
            }
        else:  # gap_analysis
            return {
                "summary": f"Accreditation and competency alignment analysis for {course_name} based on academy standards.",
                "gaps": [
                    {"requirement": "Industry Standard Tooling", "status": "Covered", "severity": "Low", "recommendation": "Maintain current curriculum."},
                    {"requirement": "Advanced Compliance Protocols", "status": "Missing", "severity": "Medium", "recommendation": "Incorporate a dedicated module."}
                ],
                "recommended_actions": [
                    "Integrate recommended modules prior to final review.",
                    "Re-run automated alignment check."
                ]
            }

    def _styles(self):
        s = getSampleStyleSheet()
        s.add(
            ParagraphStyle(
                "SectionH2",
                parent=s["Heading2"],
                textColor=colors.HexColor("#1F3A5F"),
                spaceBefore=14,
                spaceAfter=6,
            )
        )
        s.add(
            ParagraphStyle(
                "Meta", parent=s["Normal"], fontSize=9, textColor=colors.grey
            )
        )
        s.add(ParagraphStyle("Body", parent=s["BodyText"], leading=15))
        return s

    def _header(self, title, meta, styles):
        out = [Paragraph(escape(title), styles["Title"]), Spacer(1, 6)]
        if meta:
            line = " | ".join(
                f"<b>{escape(str(k))}:</b> {escape(str(v))}"
                for k, v in meta.items()
            )
            out.append(Paragraph(line, styles["Meta"]))
        out += [
            Spacer(1, 6),
            HRFlowable(width="100%", thickness=1, color=colors.grey),
            Spacer(1, 12),
        ]
        return out

    def _footer(self, styles):
        return [
            Spacer(1, 18),
            HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey),
            Paragraph(
                "Generated autonomously via REX AI RAG Knowledge Base — for internal review only. "
                "This document does not certify official accreditation.",
                styles["Meta"],
            ),
        ]

    def _bullets(self, items, styles):
        cleaned = [str(i) for i in items if str(i).strip()]
        if not cleaned:
            return Spacer(1, 1)
        return ListFlowable(
            [ListItem(Paragraph(escape(t), styles["Body"])) for t in cleaned],
            bulletType="bullet",
            start="•",
            leftIndent=14,
            bulletFontSize=10,
        )

    def _data_table(self, rows, col_widths, header_bg="#1F3A5F"):
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return t

    def _kv_table(self, pairs):
        t = Table(pairs, colWidths=[4 * cm, 12 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2F7")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return t

    def _build_curriculum_report(self, c, styles):
        out = []
        if c.get("overview"):
            out += [Paragraph("Overview", styles["SectionH2"]), Paragraph(escape(str(c["overview"])), styles["Body"])]
        if c.get("objectives"):
            out += [Paragraph("Learning Objectives", styles["SectionH2"]), self._bullets(c["objectives"], styles)]
        modules = c.get("modules") or []
        if modules:
            rows = [["#", "Module", "Topics", "Hours"]]
            for i, m in enumerate(modules, 1):
                rows.append([str(i), escape(str(m.get("title", ""))), escape(", ".join(m.get("topics", []))), str(m.get("hours", ""))])
            out += [Paragraph("Course Modules", styles["SectionH2"]), self._data_table(rows, [1 * cm, 5 * cm, 8 * cm, 2 * cm])]
        if c.get("assessments"):
            out += [Paragraph("Assessments", styles["SectionH2"]), self._bullets(c["assessments"], styles)]
        if c.get("capstone"):
            out += [Paragraph("Capstone Project", styles["SectionH2"]), Paragraph(escape(str(c["capstone"])), styles["Body"])]
        return out

    def _build_course_description(self, c, styles):
        out = []
        if c.get("pitch"):
            out += [Paragraph(escape(str(c["pitch"])), styles["Body"]), Spacer(1, 6)]
        facts = [(escape(str(k)), escape(str(c[k]))) for k in ("audience", "level", "duration", "format", "fee", "prerequisites") if c.get(k)]
        if facts:
            out += [Paragraph("Key Facts", styles["SectionH2"]), self._kv_table(facts)]
        if c.get("outcomes"):
            out += [Paragraph("What You Will Learn", styles["SectionH2"]), self._bullets(c["outcomes"], styles)]
        if c.get("careers"):
            out += [Paragraph("Career Opportunities", styles["SectionH2"]), self._bullets(c["careers"], styles)]
        return out

    def _build_gap_analysis(self, c, styles):
        out = []
        if c.get("summary"):
            out += [Paragraph("Summary", styles["SectionH2"]), Paragraph(escape(str(c["summary"])), styles["Body"])]
        gaps = c.get("gaps") or []
        if gaps:
            rows = [["Requirement", "Status", "Severity", "Recommendation"]]
            for g in gaps:
                rows.append([escape(str(g.get("requirement", ""))), escape(str(g.get("status", ""))), escape(str(g.get("severity", ""))), escape(str(g.get("recommendation", "")))])
            out += [Paragraph("Gap Details", styles["SectionH2"]), self._data_table(rows, [4.5 * cm, 2.5 * cm, 2 * cm, 7 * cm])]
        if c.get("recommended_actions"):
            out += [Paragraph("Recommended Actions", styles["SectionH2"]), self._bullets(c["recommended_actions"], styles)]
        return out