"""Small run-directory helper with immutable source capture."""

import hashlib
import shutil
from pathlib import Path
from uuid import UUID

from labpilot.models.execution import ExperimentArtifact


class ArtifactError(RuntimeError):
    pass


def create_artifacts(root: Path, research_id: UUID, experiment_id: UUID) -> ExperimentArtifact:
    directory = root.resolve() / "runs" / str(research_id) / str(experiment_id)
    if directory.exists():
        raise ArtifactError(
            f"Execution directory already exists; reconcile before retry: {directory}"
        )
    directory.mkdir(parents=True)
    (directory / "outputs").mkdir()
    artifacts = ExperimentArtifact(
        stdout_path=directory / "stdout.log",
        stderr_path=directory / "stderr.log",
        metrics_path=directory / "outputs" / "metrics.json",
        provenance_path=directory / "provenance.json",
        patch_path=directory / "patch.diff",
        actual_diff_path=directory / "actual.diff",
        source_path=directory / "source",
    )
    artifacts.stdout_path.touch()
    artifacts.stderr_path.touch()
    artifacts.patch_path.touch()
    artifacts.actual_diff_path.touch()
    return artifacts


def capture_source(worktree: Path, names: tuple[str, ...], destination: Path) -> str:
    """Export regular tracked files only, excluding Git metadata and generated outputs."""
    destination.mkdir()
    digest = hashlib.sha256()
    for name in sorted(names):
        relative = Path(name)
        if relative.is_absolute() or any(
            part in {"..", ".git", "outputs"} for part in relative.parts
        ):
            raise ArtifactError(f"Unsafe tracked path: {name}")
        source = worktree / relative
        if source.is_symlink() or not source.resolve().is_relative_to(worktree.resolve()):
            raise ArtifactError(f"Symlink source is unsupported: {name}")
        if not source.is_file():
            raise ArtifactError(f"Source is not a regular file: {name}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest.update(name.encode() + b"\0" + source.read_bytes() + b"\0")
    (destination / "outputs").mkdir()
    return digest.hexdigest()
