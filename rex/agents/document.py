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

        if not isinstance(meta, dict):
            meta = {}

        used_rag = False
        simple_lines = None

        if isinstance(content, list) and content:
            # Simple mode: a plain list of strings is rendered as paragraphs.
            if not all(isinstance(item, str) for item in content):
                return AgentResult(
                    self.name, False, message="Every content item must be a string."
                )
            simple_lines = content
        elif isinstance(content, dict) and content:
            pass  # typed layout, rendered by _build_<document_type>
        elif content in (None, [], {}):
            # No content given: build a clearly-marked draft from the knowledge base.
            course_name = str(meta.get("Course", title))
            rag_context = self._rag_context(course_name)
            used_rag = bool(rag_context)
            content = self._auto_generate_content(doc_type, title, meta, rag_context)
        else:
            return AgentResult(
                self.name,
                False,
                message="content must be a JSON object, a list of strings, or omitted.",
            )

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
            output_path = output_dir / f"{doc_type}_{safe_title}.pdf"

            styles = self._styles()
            story = []
            story += self._header(title, meta, styles)
            if simple_lines is not None:
                story += self._build_simple(simple_lines, styles)
            else:
                story += getattr(self, f"_build_{doc_type}")(content, styles)
            story += self._footer(styles, used_rag)

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

    def _rag_context(self, course_name: str) -> str:
        """First 300 chars of each knowledge-base doc that mentions the course title."""
        needle = course_name.strip().casefold()
        docs_dir = Path(__file__).resolve().parents[2] / "data" / "rag_docs"
        if not needle or not docs_dir.exists():
            return ""
        try:
            snippets = []
            for md_file in sorted(docs_dir.glob("*.md")):
                text = md_file.read_text(encoding="utf-8", errors="ignore")
                if needle in text.casefold():
                    snippets.append(text[:300])
            return " ".join(snippets)
        except OSError:
            return ""

    def _auto_generate_content(self, doc_type: str, title: str, meta: dict, rag_context: str) -> dict:
        """Draft content used only when the caller supplied none.

        Facts the agent cannot know (fee, duration, prerequisites) are left as
        'To be confirmed' instead of being invented.
        """
        course_name = meta.get("Course", title)
        audience = meta.get("Audience", "To be confirmed")
        level = meta.get("Level", "To be confirmed")
        base_overview = rag_context if rag_context else f"Draft training program for {course_name}."

        if doc_type == "curriculum_report":
            return {
                "overview": f"{base_overview[:300]} (Draft - to be completed by the course owner.)",
                "objectives": [f"To be defined for {course_name}"],
                "modules": [],
                "assessments": [],
                "capstone": "",
            }
        elif doc_type == "course_description":
            return {
                "pitch": f"{course_name} - draft course description.",
                "audience": audience,
                "level": level,
                "duration": "To be confirmed",
                "format": "To be confirmed",
                "fee": "To be confirmed",
                "prerequisites": "To be confirmed",
                "outcomes": [],
                "careers": [],
            }
        else:  # gap_analysis
            return {
                "summary": f"Draft gap analysis for {course_name}. No gaps have been entered yet.",
                "gaps": [],
                "recommended_actions": [],
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
        s.add(ParagraphStyle("Cell", parent=s["Normal"], fontSize=9, leading=11))
        s.add(
            ParagraphStyle(
                "CellHead", parent=s["Cell"], textColor=colors.white,
                fontName="Helvetica-Bold",
            )
        )
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

    def _footer(self, styles, used_rag=False):
        note = (
            "Draft built from the REX AI knowledge base - " if used_rag
            else "Generated by REX AI - "
        )
        return [
            Spacer(1, 18),
            HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey),
            Paragraph(
                note + "for internal review only. "
                "This document does not certify official accreditation.",
                styles["Meta"],
            ),
        ]

    @staticmethod
    def _as_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]  # a lone string must not be split into characters

    def _bullets(self, items, styles):
        cleaned = [str(i) for i in self._as_list(items) if str(i).strip()]
        if not cleaned:
            return Spacer(1, 1)
        return ListFlowable(
            [ListItem(Paragraph(escape(t), styles["Body"])) for t in cleaned],
            bulletType="bullet",
            start="•",
            leftIndent=14,
            bulletFontSize=10,
        )

    def _cell(self, value, styles, head=False):
        """Table cell as a Paragraph, so text wraps and special characters render correctly."""
        return Paragraph(escape(str(value)), styles["CellHead" if head else "Cell"])

    def _data_table(self, rows, col_widths, styles, header_bg="#1F3A5F"):
        data = [
            [self._cell(c, styles, head=(r == 0)) for c in row]
            for r, row in enumerate(rows)
        ]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return t

    def _kv_table(self, pairs, styles):
        data = [
            [self._cell(k, styles), self._cell(v, styles)]
            for k, v in pairs
        ]
        t = Table(data, colWidths=[4 * cm, 12 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2F7")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return t

    def _build_simple(self, lines, styles):
        out = []
        for line in lines:
            out += [Paragraph(escape(line), styles["Body"]), Spacer(1, 6)]
        return out

    def _build_curriculum_report(self, c, styles):
        out = []
        if c.get("overview"):
            out += [Paragraph("Overview", styles["SectionH2"]), Paragraph(escape(str(c["overview"])), styles["Body"])]
        if c.get("objectives"):
            out += [Paragraph("Learning Objectives", styles["SectionH2"]), self._bullets(c["objectives"], styles)]
        modules = [m for m in self._as_list(c.get("modules")) if isinstance(m, dict)]
        if modules:
            rows = [["#", "Module", "Topics", "Hours"]]
            for i, m in enumerate(modules, 1):
                topics = ", ".join(str(t) for t in self._as_list(m.get("topics")))
                hours = m.get("hours", m.get("duration_hours", ""))
                rows.append([str(i), m.get("title", ""), topics, hours])
            out += [Paragraph("Course Modules", styles["SectionH2"]), self._data_table(rows, [1 * cm, 5 * cm, 8 * cm, 2 * cm], styles)]
        if c.get("assessments"):
            out += [Paragraph("Assessments", styles["SectionH2"]), self._bullets(c["assessments"], styles)]
        if c.get("capstone"):
            out += [Paragraph("Capstone Project", styles["SectionH2"]), Paragraph(escape(str(c["capstone"])), styles["Body"])]
        return out

    def _build_course_description(self, c, styles):
        out = []
        if c.get("pitch"):
            out += [Paragraph(escape(str(c["pitch"])), styles["Body"]), Spacer(1, 6)]
        facts = [(k.capitalize(), c[k]) for k in ("audience", "level", "duration", "format", "fee", "prerequisites") if c.get(k)]
        if facts:
            out += [Paragraph("Key Facts", styles["SectionH2"]), self._kv_table(facts, styles)]
        if c.get("outcomes"):
            out += [Paragraph("What You Will Learn", styles["SectionH2"]), self._bullets(c["outcomes"], styles)]
        if c.get("careers"):
            out += [Paragraph("Career Opportunities", styles["SectionH2"]), self._bullets(c["careers"], styles)]
        return out

    def _build_gap_analysis(self, c, styles):
        out = []
        if c.get("summary"):
            out += [Paragraph("Summary", styles["SectionH2"]), Paragraph(escape(str(c["summary"])), styles["Body"])]
        gaps = [g for g in self._as_list(c.get("gaps")) if isinstance(g, dict)]
        if gaps:
            rows = [["Requirement", "Status", "Severity", "Recommendation"]]
            for g in gaps:
                rows.append([g.get("requirement", ""), g.get("status", ""), g.get("severity", ""), g.get("recommendation", "")])
            out += [Paragraph("Gap Details", styles["SectionH2"]), self._data_table(rows, [4.5 * cm, 2.5 * cm, 2 * cm, 7 * cm], styles)]
        if c.get("recommended_actions"):
            out += [Paragraph("Recommended Actions", styles["SectionH2"]), self._bullets(c["recommended_actions"], styles)]
        return out
