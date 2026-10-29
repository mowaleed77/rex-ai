
from pathlib import Path



from rex.agents.document import DocumentAgent


def test_generate_three_pdf_types(tmp_path):
    agent = DocumentAgent()

    for document_type in [
        "curriculum_report",
        "course_description",
        "gap_analysis"
    ]:
        result = agent.run({
            "document_type": document_type,
            "title": "Test Report",
            "content": ["First section", "Second section"],
            "output_dir": str(tmp_path)
        })

        assert result.ok
        pdf_path = Path(result.output["file_path"])
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0


def test_unsupported_document_type():
    result = DocumentAgent().run({
        "document_type": "unknown",
        "content": ["Test"]
    })

    assert not result.ok


def test_empty_content():
    result = DocumentAgent().run({
        "document_type": "curriculum_report",
        "content": []
    })

    assert not result.ok
