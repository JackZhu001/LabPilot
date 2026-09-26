import json

import pytest
from typer.testing import CliRunner

from labpilot.cli.app import app
from labpilot.graph.workflow import execute
from labpilot.models.common import MetricDirection
from labpilot.models.experiments import Baseline
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.reporting import benchmark, evaluate_run, fingerprint, research_report


def test_snapshot_reports_and_benchmark(tmp_path):
    path = tmp_path / "reports.sqlite3"
    repository = SQLiteResearchRepository(path)
    initial = repository.create(
        ResearchState(
            research_goal="Minimize loss",
            baseline=Baseline(
                metric_name="loss",
                value=0.8,
                direction=MetricDirection.MINIMIZE,
            ),
        )
    )
    completed = execute(repository, initial.research_id)
    report = research_report(completed)
    assert report == research_report(ResearchState.model_validate(report["state"]))
    legacy = completed.model_dump(mode="json")
    for paper in legacy["papers"]:
        paper.pop("retrieved_at", None)
    assert research_report(ResearchState.model_validate(legacy)) == research_report(
        ResearchState.model_validate(legacy)
    )
    summary = report["summary"]
    assert summary["best"] < summary["baseline"]
    assert summary["improvement"] > 0
    assert summary["runtime_seconds"] is None
    assert fingerprint(completed) in report["markdown"]
    assert evaluate_run(initial)["best"] is None
    assert benchmark([initial])["groups"][0]["strategies"][0]["mean_improvement"] is None
    result = benchmark([completed, completed])
    assert len(result["runs"]) == 1
    assert result["groups"][0]["strategies"][0]["keep_rate"] == 1
    with pytest.raises(ValueError, match="Conflicting snapshots"):
        benchmark([initial, completed])
    runner = CliRunner()
    exported = runner.invoke(
        app, ["report", str(completed.research_id), "--db", str(path), "--format", "json"]
    )
    assert exported.exit_code == 0, exported.output
    assert json.loads(exported.output) == report
    compared = runner.invoke(app, ["benchmark", "--db", str(path)])
    assert compared.exit_code == 0, compared.output
    assert json.loads(compared.output) == result
