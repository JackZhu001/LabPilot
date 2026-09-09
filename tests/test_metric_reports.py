from pathlib import Path

import pytest

from labpilot.execution.metrics import MetricsError, MetricsParser
from labpilot.models.state import ResearchState


def test_metric_report_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    path.write_text(
        '{"schema_version":1,"metrics":{"validation_accuracy":0.91,"validation_loss":0.2},"metadata":{"seed":42,"epochs":2}}'
    )
    report = MetricsParser().parse(path, "validation_accuracy")
    assert report.metrics["validation_accuracy"] == 0.91
    assert report.metadata.seed == 42


@pytest.mark.parametrize(
    "raw",
    [
        "broken",
        "{}",
        '{"schema_version":2,"metrics":{"accuracy":0.9}}',
        '{"schema_version":1,"metrics":{"accuracy":NaN}}',
        '{"schema_version":1,"metrics":{"accuracy":Infinity}}',
        '{"schema_version":1,"metrics":{"accuracy":"0.9"}}',
        '{"schema_version":1,"metrics":{"accuracy":true}}',
        '{"schema_version":1,"metrics":{"accuracy":0.9,"accuracy":0.8}}',
        '{"schema_version":1,"metrics":{"other":0.9}}',
        '{"schema_version":1,"metrics":{}}',
        '{"schema_version":1,"metrics":{"accuracy":0.9},"extra":1}',
    ],
)
def test_invalid_reports(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "metrics.json"
    path.write_text(raw)
    with pytest.raises(MetricsError):
        MetricsParser().parse(path, "accuracy")


def test_missing_and_symlink_reports(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    with pytest.raises(MetricsError, match="Missing"):
        MetricsParser().parse(path, "accuracy")
    target = tmp_path / "other"
    target.write_text("{}")
    path.symlink_to(target)
    with pytest.raises(MetricsError, match="unsafe"):
        MetricsParser().parse(path, "accuracy")


def test_old_snapshot_loads_without_migration() -> None:
    old = ResearchState(research_goal="Original Phase 1 run").model_dump(mode="json")
    old.pop("execution")
    old.pop("baseline_experiment_id")
    restored = ResearchState.model_validate(old)
    assert restored.execution.environment.value == "fake"
