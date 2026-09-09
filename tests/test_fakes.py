from uuid import uuid4

import pytest

from labpilot.models.common import ExperimentStatus, FakeOutcome, MetricDirection
from labpilot.models.experiments import Baseline, Experiment
from labpilot.models.state import SimulationConfig
from labpilot.services.fakes import FakeExperimentRunner, fake_services


def test_reproducible_provenance() -> None:
    research_id = uuid4()
    services = fake_services(SimulationConfig())
    papers = services.literature.retrieve(research_id, "Goal")
    assert papers == services.literature.retrieve(research_id, "Goal")
    claims, evidence = services.evidence.extract(papers)
    assert claims[0].paper_id == papers[0].id and evidence[0].claim_id == claims[0].id
    first = services.hypothesis.generate(research_id, "Goal", evidence, 1)
    assert first == services.hypothesis.generate(research_id, "Goal", evidence, 1)
    assert first.id != services.hypothesis.generate(research_id, "Goal", evidence, 2).id
    assert first.evidence_ids == (evidence[0].id,)


@pytest.mark.parametrize("direction", list(MetricDirection))
@pytest.mark.parametrize("outcome", list(FakeOutcome))
def test_controlled_outcomes(direction: MetricDirection, outcome: FakeOutcome) -> None:
    runner = FakeExperimentRunner(SimulationConfig(outcomes=(outcome,)))
    baseline = Baseline(direction=direction)
    experiment = Experiment(hypothesis_id=uuid4(), sequence=7)
    result = runner.run(experiment, baseline)
    assert result == runner.run(experiment, baseline)
    if outcome == FakeOutcome.FAIL:
        assert result.status == ExperimentStatus.FAILED
    else:
        assert result.status == ExperimentStatus.SUCCEEDED
        delta = result.value - baseline.value
        if direction == MetricDirection.MINIMIZE:
            delta *= -1
        expected = {
            FakeOutcome.IMPROVE: 0.02,
            FakeOutcome.REGRESS: -0.02,
            FakeOutcome.INCONCLUSIVE: 0,
        }
        assert delta == pytest.approx(expected[outcome])
