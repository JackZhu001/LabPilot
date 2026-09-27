import json
import re
from pathlib import Path
from uuid import uuid4

from typer.testing import CliRunner

from labpilot.cli.app import app

runner = CliRunner()


def test_cli_resume_status_and_runs(tmp_path: Path) -> None:
    db = str(tmp_path / "cli.sqlite3")
    assert runner.invoke(app, ["init", "--db", db]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "run",
            "--goal",
            "Does dropout help?",
            "--db",
            db,
            "--stop-after",
            "4",
            "--outcomes",
            "inconclusive,improve",
        ],
    )
    assert result.exit_code == 0, result.output
    research_id = re.search(r"Research ID: (\S+)", result.output).group(1)
    assert "Status: PAUSED" in result.output
    resumed = runner.invoke(app, ["resume", research_id, "--db", db])
    assert resumed.exit_code == 0, resumed.output
    assert "Decision: KEEP" in resumed.output and "Iteration: 2/3" in resumed.output
    status = runner.invoke(app, ["status", research_id, "--db", db, "--json"])
    assert status.exit_code == 0, status.output
    state = json.loads(status.output)
    assert state["decision"] == "KEEP" and len(state["experiments"]) == 2
    listing = runner.invoke(app, ["runs", "--db", db])
    assert listing.exit_code == 0 and research_id in listing.output


def test_cli_bad_input(tmp_path: Path) -> None:
    db = str(tmp_path / "cli.sqlite3")
    for args in [
        ["run", "--goal", "Goal", "--outcomes", "bad"],
        ["run", "--goal", "Goal", "--stop-after", "0"],
        ["run", "--goal", "   "],
        ["run", "--goal", "Goal", "--max-iterations", "-1"],
        ["run", "--goal", "Goal", "--hpo"],
        ["run", "--goal", "Goal", "--agent"],
        ["status", "invalid-uuid"],
        ["resume", str(uuid4())],
    ]:
        result = runner.invoke(app, [*args, "--db", db])
        assert result.exit_code != 0 and "Error" in result.output


def test_judge_evidence_calls_jev_and_returns_typed_result(monkeypatch) -> None:
    from types import SimpleNamespace

    class Usage:
        def model_dump(self):
            return {"input_tokens": 50, "output_tokens": 12}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def system_one(self, **kwargs):
            assert kwargs["model"] == "jev-latest"
            assert set(kwargs["questions"]) == {"relation", "strength", "relevant"}
            return SimpleNamespace(
                model="jev-latest",
                usage=Usage(),
                choices={"relation": SimpleNamespace(choice="supports", confidence=0.9)},
                scores={"strength": SimpleNamespace(score=3.7, confidence=0.8)},
                nouls={"relevant": SimpleNamespace(noul=0.96)},
            )

    monkeypatch.setattr("labpilot.cli.app.TypeSafeClient", Client)
    result = runner.invoke(
        app,
        ["judge-evidence", "--hypothesis", "dropout helps", "--claim", "Accuracy rose."],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["relation"] == "supports" and report["strength"] == 3.7
    assert report["relevance_probability"] == 0.96
