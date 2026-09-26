"""Docker CLI adapter. No Git logic, graph dependency, shell, or log metric parsing."""

import os
import subprocess
from dataclasses import dataclass
from uuid import UUID

from labpilot.models.execution import ExecutionConfig, ExperimentArtifact


class DockerError(RuntimeError):
    def __init__(self, message: str, *, cleanup_errors: tuple[str, ...] = ()) -> None:
        self.cleanup_errors = cleanup_errors
        super().__init__(message)


@dataclass(frozen=True)
class ContainerResult:
    container_id: str
    exit_code: int | None
    timed_out: bool
    cleanup_errors: tuple[str, ...] = ()
    failure_reason: str | None = None


class DockerClient:
    def _capture(self, *args: str, timeout: float = 30) -> str:
        try:
            result = subprocess.run(
                ["docker", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DockerError(str(exc)) from exc
        if result.returncode != 0:
            raise DockerError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def prepare_image(self, config: ExecutionConfig, artifacts: ExperimentArtifact) -> str:
        if config.build_image:
            try:
                with (
                    artifacts.stdout_path.open("ab") as stdout,
                    artifacts.stderr_path.open("ab") as stderr,
                ):
                    result = subprocess.run(
                        ["docker", "build", "--tag", config.image, str(artifacts.source_path)],
                        stdout=stdout,
                        stderr=stderr,
                        timeout=config.build_timeout_seconds,
                        check=False,
                    )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise DockerError(f"Docker build failed: {exc}") from exc
            if result.returncode != 0:
                raise DockerError(f"Docker build failed (exit {result.returncode}); see stderr.log")
        return self._capture("image", "inspect", "--format", "{{.Id}}", config.image)

    def run(
        self,
        config: ExecutionConfig,
        artifacts: ExperimentArtifact,
        experiment_id: UUID,
        image_id: str,
        seed: int,
        metric_name: str = "validation_accuracy",
        direction: str = "MAXIMIZE",
    ) -> ContainerResult:
        name = f"labpilot-{experiment_id}"
        command = config.training_command
        # Numeric host identity keeps bind-mounted artifacts readable on Linux too.
        args = (
            "create",
            "--name",
            name,
            "--label",
            f"labpilot.experiment_id={experiment_id}",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "128",
            "--cpus",
            str(config.cpus),
            "--memory",
            f"{config.memory_mb}m",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
            "--workdir",
            "/workspace",
            "--mount",
            f"type=bind,src={artifacts.source_path},dst=/workspace,readonly",
            "--mount",
            f"type=bind,src={artifacts.metrics_path.parent},dst=/workspace/outputs",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            f"LABPILOT_SEED={seed}",
            "--env",
            f"LABPILOT_METRIC_NAME={metric_name}",
            "--env",
            f"LABPILOT_METRIC_DIRECTION={direction.lower()}",
            "--env",
            "OMP_NUM_THREADS=2",
            "--entrypoint",
            command[0],
            image_id,
            *command[1:],
        )
        try:
            container_id = self._capture(*args, timeout=120)
        except DockerError as exc:
            errors: list[str] = []
            # A timed-out create may still have allocated a container in the daemon.
            try:
                owner = self._capture(
                    "inspect", "--format", '{{index .Config.Labels "labpilot.experiment_id"}}', name
                )
                if owner == str(experiment_id):
                    self._capture("rm", "--force", name)
                else:
                    errors.append(f"Container ownership could not be verified: {name}")
            except DockerError as cleanup:
                # A failed create commonly has no container; retain that diagnostic.
                errors.append(f"Creation cleanup: {cleanup}")
            raise DockerError(str(exc), cleanup_errors=tuple(errors)) from exc
        exit_code: int | None = None
        timed_out = False
        failure: str | None = None
        cleanup_errors: list[str] = []
        try:
            with (
                artifacts.stdout_path.open("ab") as stdout,
                artifacts.stderr_path.open("ab") as stderr,
            ):
                try:
                    process = subprocess.run(
                        ["docker", "start", "--attach", container_id],
                        stdout=stdout,
                        stderr=stderr,
                        timeout=config.timeout_seconds,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self._capture("kill", container_id)
                else:
                    # Docker start's own return code is not the scientific result.
                    raw_exit = self._capture(
                        "inspect", "--format", "{{.State.ExitCode}}", container_id
                    )
                    exit_code = int(raw_exit)
                    if process.returncode and exit_code == 0:
                        raise DockerError(f"Docker attach failed with exit {process.returncode}")
        except (DockerError, OSError, ValueError) as exc:
            failure = f"Docker execution failed: {exc}"
        finally:
            try:
                self._capture("rm", "--force", container_id)
            except DockerError as exc:
                cleanup_errors.append(str(exc))
        return ContainerResult(container_id, exit_code, timed_out, tuple(cleanup_errors), failure)
