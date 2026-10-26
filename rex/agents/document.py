
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from .base import Agent, AgentResult


class DocumentAgent(Agent):
    name = "document"

    def run(self, task: dict) -> AgentResult:
        document_type = task.get("document_type")
        title = task.get("title", "REX Academy Report")
        content = task.get("content", [])
        output_dir = Path(task.get("output_dir", "generated_docs"))

        supported_types = {
            "curriculum_report",
            "course_description",
            "gap_analysis"
        }

        if document_type not in supported_types:
            return AgentResult(
                self.name,
                False,
                message=(
                    "Unsupported document_type. Choose: "
                    + ", ".join(sorted(supported_types))
                )
            )

        if not isinstance(content, list) or not content:
            return AgentResult(
                self.name,
                False,
                message="Please provide content as a non-empty list of strings."
            )

        if not all(isinstance(item, str) for item in content):
            return AgentResult(
                self.name,
                False,
                message="Every content item must be a string."
            )

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{document_type}.pdf"

            styles = getSampleStyleSheet()
            story = [
                Paragraph(escape(title), styles["Title"]),
                Spacer(1, 20)
            ]

            for item in content:
                story.append(Paragraph(escape(item), styles["BodyText"]))
                story.append(Spacer(1, 10))

            SimpleDocTemplate(
                str(output_path),
                pagesize=A4
            ).build(story)

            return AgentResult(
                self.name,
                True,
                output={
                    "document_type": document_type,
                    "file_path": str(output_path.resolve())
                },
                message=f"PDF created successfully: {output_path.resolve()}"
            )

        except Exception as error:
            return AgentResult(
                self.name,
                False,
                message=f"Could not generate PDF: {error}"
            )
