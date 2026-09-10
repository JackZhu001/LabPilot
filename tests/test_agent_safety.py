from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from labpilot.agent.patches import PatchPolicyError, PatchValidator
from labpilot.agent.repository import RepositoryInspector
from labpilot.execution.git import WorktreeManager, git
from labpilot.llm.models import PatchProposal
from labpilot.services.real import prepare_example


def repository(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "train.py").write_text("print('safe')\n")
    (source / "README.md").write_text("Fixture\n")
    (source / ".env").write_text("SECRET=never-send\n")
    (source / "credentials.json").write_text('{"token":"never-send"}\n')
    (source / "model.bin").write_bytes(b"\x00\x01")
    return prepare_example(source, tmp_path / "baseline")


def test_repository_context_is_bounded_and_excludes_secrets(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    sha = git(repo, "rev-parse", "HEAD").strip()
    context = RepositoryInspector(max_context_characters=1000).inspect(repo, sha)
    assert "train.py" in context.file_tree
    assert ".env" not in context.file_tree and "credentials.json" not in context.file_tree
    assert "never-send" not in context.content and len(context.content) <= 1000


def proposal(sha: str, diff: str, target: str = "train.py") -> PatchProposal:
    return PatchProposal(
        hypothesis_id=uuid4(),
        target_files=(target,),
        base_commit_sha=sha,
        unified_diff=diff,
        explanation="Fixture change",
        risk_notes=(),
    )


def test_patch_policy_validates_in_disposable_worktree(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    sha = git(repo, "rev-parse", "HEAD").strip()
    validator = PatchValidator(WorktreeManager(repo, tmp_path / "worktrees"))
    diff = "--- a/train.py\n+++ b/train.py\n@@ -1 +1 @@\n-print('safe')\n+print('better')\n"
    actual = validator.validate(
        proposal(sha, diff), expected_sha=sha, allowed_targets=("train.py",)
    )
    assert "+print('better')" in actual
    assert (repo / "train.py").read_text() == "print('safe')\n"
    assert git(repo, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    ("diff", "target", "expected_sha"),
    [
        ("not a patch", "train.py", None),
        ("--- a/train.py\n+++ b/../escape\n@@ -1 +1 @@\n-a\n+b\n", "../escape", None),
        ("--- a/.env\n+++ b/.env\n@@ -1 +1 @@\n-a\n+b\n", ".env", None),
        (
            "--- a/train.py\n+++ b/train.py\n@@ -1 +1 @@\n-print('safe')\n+os.system('rm -rf /')\n",
            "train.py",
            None,
        ),
        ("--- a/train.py\n+++ b/train.py\n@@ -1 +1 @@\n-a\n+b\n", "train.py", "0" * 40),
    ],
)
def test_unsafe_or_malformed_patch_rejected(
    tmp_path: Path, diff: str, target: str, expected_sha: str | None
) -> None:
    repo = repository(tmp_path)
    sha = git(repo, "rev-parse", "HEAD").strip()
    validator = PatchValidator(WorktreeManager(repo, tmp_path / "worktrees"))
    with pytest.raises((PatchPolicyError, ValueError)):
        validator.validate(
            proposal(expected_sha or sha, diff, target),
            expected_sha=sha,
            allowed_targets=(target,),
        )
