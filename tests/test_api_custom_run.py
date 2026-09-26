import base64

import pytest

from labpilot.api import research_preview, uploaded_paper


def test_uploaded_markdown_becomes_a_source_tracked_paper() -> None:
    body = "A useful paper abstract with enough content to extract a supported claim."
    paper = uploaded_paper("../study.md", base64.b64encode(body.encode()).decode())

    assert paper.title == "study"
    assert paper.source_provider == "user_upload"
    assert paper.abstract is None
    assert paper.full_text_excerpt == body


def test_uploaded_paper_rejects_unsupported_and_unreadable_files() -> None:
    with pytest.raises(ValueError, match="PDF, Markdown, or text"):
        uploaded_paper(
            "notes.docx", base64.b64encode(b"long enough content for this file").decode()
        )
    with pytest.raises(ValueError, match="too little readable text"):
        uploaded_paper("empty.txt", base64.b64encode(b"tiny").decode())


def test_research_preview_inspects_default_baseline_and_objective() -> None:
    preview = research_preview(
        {
            "goal": "Improve validation accuracy",
            "metric_name": "validation_loss",
            "direction": "MINIMIZE",
            "max_iterations": 2,
            "max_literature_queries": 3,
            "max_retrieved_papers": 8,
            "seed": 123,
            "constraints": "Prefer simple, reproducible interventions.",
            "papers": ["study.pdf"],
            "change_type": "CONFIG_ONLY",
        }
    )

    assert preview["baseline"]["name"] == "MNIST baseline"
    assert preview["baseline"]["commit_sha"]
    assert preview["objective"] == {"metric_name": "validation_loss", "direction": "MINIMIZE"}
    assert preview["papers"] == ["study.pdf"]
    assert preview["seed"] == 123
    assert preview["constraints"] == "Prefer simple, reproducible interventions."
    assert preview["literature"] == {
        "providers": ["arxiv", "semantic_scholar"],
        "max_queries": 3,
        "max_papers": 8,
    }
    assert preview["max_experiments"] == 3
    assert preview["change_type"] == "CONFIG_ONLY"
    assert preview["warnings"] == []


def test_default_baseline_rejects_unsupported_objective() -> None:
    with pytest.raises(ValueError, match="included MNIST baseline supports"):
        research_preview({"goal": "Improve results", "metric_name": "custom_score"})


def test_default_baseline_supports_loss_minimization() -> None:
    preview = research_preview(
        {
            "goal": "Reduce validation loss",
            "metric_name": "validation_loss",
            "direction": "MINIMIZE",
        }
    )

    assert preview["objective"] == {"metric_name": "validation_loss", "direction": "MINIMIZE"}
    assert preview["warnings"] == []
