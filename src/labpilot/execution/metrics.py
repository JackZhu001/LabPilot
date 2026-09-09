"""Strict parsing at the training process boundary."""

import json
from pathlib import Path

from pydantic import ValidationError

from labpilot.models.execution import MetricReport


class MetricsError(ValueError):
    pass


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MetricsError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


class MetricsParser:
    """Read a bounded regular JSON file and require the selected primary metric."""

    def parse(self, path: Path, primary_metric: str) -> MetricReport:
        try:
            if path.is_symlink() or not path.is_file():
                raise MetricsError("Missing or unsafe metrics.json")
            if path.stat().st_size > 1024 * 1024:
                raise MetricsError("metrics.json exceeds the 1 MiB limit")
            report = MetricReport.model_validate(
                json.loads(path.read_text(), object_pairs_hook=_unique_keys)
            )
            if primary_metric not in report.metrics:
                raise MetricsError(f"Missing primary metric: {primary_metric}")
            return report
        except (OSError, ValueError, ValidationError) as exc:
            raise MetricsError(f"Invalid metrics report: {exc}") from exc
