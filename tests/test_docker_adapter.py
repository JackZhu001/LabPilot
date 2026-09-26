import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from labpilot.execution.artifacts import create_artifacts
from labpilot.execution.docker import DockerClient, DockerError
from labpilot.models.execution import ExecutionConfig


@pytest.mark.parametrize("timeout", [False, True])
def test_container_limits_exit_and_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: bool
) -> None:
    client = DockerClient()
    calls: list[tuple[str, ...]] = []

    def capture(*args: str, **kwargs: object) -> str:
        calls.append(args)
        return "7" if args[0] == "inspect" else "container-id"

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        if timeout:
            raise subprocess.TimeoutExpired("docker start", 1)
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(client, "_capture", capture)
    monkeypatch.setattr(subprocess, "run", run)
    artifacts = create_artifacts(tmp_path, uuid4(), uuid4())
    result = client.run(
        ExecutionConfig(), artifacts, uuid4(), "sha256:image", 42,
        metric_name="validation_loss", direction="MINIMIZE",
    )
    create = calls[0]
    assert create[create.index("--network") + 1] == "none"
    assert "--read-only" in create and "--cpus" in create and "--memory" in create
    assert not any("docker.sock" in arg for arg in create)
    assert "LABPILOT_METRIC_NAME=validation_loss" in create
    assert "LABPILOT_METRIC_DIRECTION=minimize" in create
    assert result.timed_out == timeout
    assert result.exit_code == (None if timeout else 7)
    assert calls[-1] == ("rm", "--force", "container-id")
    if timeout:
        assert ("kill", "container-id") in calls


def test_container_cleanup_error_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = DockerClient()

    def capture(*args: str, **kwargs: object) -> str:
        if args[0] == "rm":
            raise DockerError("Cannot remove container")
        return "0" if args[0] == "inspect" else "container-id"

    monkeypatch.setattr(client, "_capture", capture)
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0)
    )
    result = client.run(
        ExecutionConfig(), create_artifacts(tmp_path, uuid4(), uuid4()), uuid4(), "image", 42
    )
    assert result.exit_code == 0 and result.cleanup_errors == ("Cannot remove container",)


def test_create_timeout_cleans_only_owned_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = DockerClient()
    identity = uuid4()
    calls: list[tuple[str, ...]] = []

    def capture(*args: str, **kwargs: object) -> str:
        calls.append(args)
        if args[0] == "create":
            raise DockerError("Create timed out")
        return str(identity)

    monkeypatch.setattr(client, "_capture", capture)
    with pytest.raises(DockerError, match="timed out"):
        client.run(
            ExecutionConfig(), create_artifacts(tmp_path, uuid4(), identity), identity, "image", 42
        )
    assert calls[-1] == ("rm", "--force", f"labpilot-{identity}")


def test_create_failure_does_not_remove_unowned_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = DockerClient()
    calls: list[tuple[str, ...]] = []

    def capture(*args: str, **kwargs: object) -> str:
        calls.append(args)
        if args[0] == "create":
            raise DockerError("Name conflict")
        return "someone-else"

    monkeypatch.setattr(client, "_capture", capture)
    with pytest.raises(DockerError) as failure:
        client.run(
            ExecutionConfig(), create_artifacts(tmp_path, uuid4(), uuid4()), uuid4(), "image", 42
        )
    assert not any(call[0] == "rm" for call in calls)
    assert failure.value.cleanup_errors
