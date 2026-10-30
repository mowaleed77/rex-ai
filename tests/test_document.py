"""Smoke test for the Document agent — proves the 3 PDFs differ.

Run:  python tests/test_document_agent.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rex.agents.orchestrator import Orchestrator  # noqa: E402

OUT = Path(__file__).resolve().parent / "_doc_out"
OUT.mkdir(exist_ok=True)

CASES = {
    "curriculum_report": {
        "overview": "12-week program.",
        "objectives": ["Explain ML", "Build a model"],
        "modules": [
            {"title": "Python", "topics": ["NumPy", "Pandas"], "hours": 12},
            {"title": "ML", "topics": ["Regression"], "hours": 18},
        ],
        "assessments": ["Quizzes", "Project"],
        "capstone": "Deploy a classifier.",
    },
    "course_description": {
        "pitch": "Start your AI career in 12 weeks.",
        "audience": "Career switchers",
        "level": "Beginner",
        "duration": "12 weeks",
        "format": "Online",
        "fee": "EGP 8,000",
        "prerequisites": "Basic Python",
        "outcomes": ["Train models", "Evaluate performance"],
        "careers": ["Junior ML Engineer"],
    },
    "gap_analysis": {
        "summary": "3 of 8 covered.",
        "gaps": [
            {"requirement": "Data ethics", "status": "Missing", "severity": "High",
             "recommendation": "Add a module."},
        ],
        "recommended_actions": ["Revise module 4"],
    },
}


def main():
    rex = Orchestrator()
    sizes = {}
    for dtype, content in CASES.items():
        res = rex.dispatch("document", {
            "document_type": dtype,
            "title": f"{dtype} — test",
            "metadata": {"Course": "AI Fundamentals", "Date": "2026-10-25"},
            "content": content,
            "output_dir": str(OUT),
        })
        assert res.ok, f"[{dtype}] agent failed: {res.message}"
        path = Path(res.output["file_path"])
        assert path.exists(), f"[{dtype}] file does not exist: {path}"
        sizes[dtype] = path.stat().st_size
        print(f"[OK] {dtype:22s} -> {path.name} ({sizes[dtype]:,} bytes)")

    assert len(set(sizes.values())) > 1, (
        "All three PDFs have identical size — layouts are not diverging. "
        f"Sizes: {sizes}"
    )
    print("\nAll three PDFs exist and differ in size. ✅")
    print("Inspect them manually at:", OUT)


if __name__ == "__main__":
    main()