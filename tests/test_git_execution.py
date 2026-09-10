from pathlib import Path
from uuid import uuid4

import pytest

from labpilot.execution.git import GitError, WorktreeManager, git
from labpilot.services.real import predefined_dropout_patch, prepare_example


@pytest.fixture()
def baseline_repo(tmp_path: Path) -> Path:
    source = tmp_path / "template"
    source.mkdir()
    (source / "config.yaml").write_text("seed: 42\ndropout: 0.0\n")
    (source / "train.py").write_text("print('fixture')\n")
    return prepare_example(source, tmp_path / "baseline")


def test_worktree_patch_and_baseline_integrity(baseline_repo: Path, tmp_path: Path) -> None:
    manager = WorktreeManager(baseline_repo, tmp_path / "worktrees")
    sha = manager.validate_clean_baseline()
    original = (baseline_repo / "config.yaml").read_bytes()
    worktree = manager.create_worktree(uuid4(), sha)
    assert manager.get_head_sha(worktree) == sha
    manager.apply_patch(worktree, predefined_dropout_patch(baseline_repo), sha)
    assert "dropout: 0.3" in (worktree / "config.yaml").read_text()
    assert "+dropout: 0.3" in manager.get_diff(worktree)
    assert (baseline_repo / "config.yaml").read_bytes() == original
    assert manager.validate_clean_baseline(sha) == sha
    manager.cleanup_worktree(worktree)
    assert not worktree.exists()
    assert manager.validate_clean_baseline() == sha


def test_worktree_recounts_incorrect_hunk_lengths(baseline_repo: Path, tmp_path: Path) -> None:
    manager = WorktreeManager(baseline_repo, tmp_path / "worktrees")
    sha = manager.validate_clean_baseline()
    worktree = manager.create_worktree(uuid4(), sha)
    patch = "\n".join(
        (
            "--- a/train.py",
            "+++ b/train.py",
            "@@ -1,2 +1,3 @@",
            " print('fixture')",
            "+print('recounted')",
            "",
        )
    )
    manager.apply_patch(worktree, patch, sha)
    assert (worktree / "train.py").read_text() == "print('fixture')\nprint('recounted')\n"
    manager.cleanup_worktree(worktree)


def test_patch_conflict_and_base_mismatch(baseline_repo: Path, tmp_path: Path) -> None:
    manager = WorktreeManager(baseline_repo, tmp_path / "worktrees")
    sha = manager.get_head_sha()
    worktree = manager.create_worktree(uuid4(), sha)
    patch = predefined_dropout_patch(baseline_repo)
    with pytest.raises(GitError, match="base commit"):
        manager.apply_patch(worktree, patch, "0" * 40)
    manager.apply_patch(worktree, patch, sha)
    with pytest.raises(GitError):
        manager.apply_patch(worktree, patch, sha)
    manager.cleanup_worktree(worktree)


@pytest.mark.parametrize(
    "patch",
    [
        "",
        "not a patch",
        "--- /etc/passwd\n+++ /etc/passwd\n@@ -1 +1 @@\n-a\n+b\n",
        "--- a/../escape\n+++ b/../escape\n@@ -1 +1 @@\n-a\n+b\n",
        "--- a/.git/config\n+++ b/.git/config\n@@ -1 +1 @@\n-a\n+b\n",
        "--- a/outputs/metrics.json\n+++ b/outputs/metrics.json\n@@ -1 +1 @@\n-a\n+b\n",
        "new file mode 120000\n--- /dev/null\n+++ b/link\n@@ -0,0 +1 @@\n+/etc/passwd\n",
    ],
)
def test_patch_policy(patch: str) -> None:
    with pytest.raises(GitError):
        WorktreeManager.validate_patch(patch)


def test_dirty_baseline_rejected(baseline_repo: Path, tmp_path: Path) -> None:
    (baseline_repo / "untracked").touch()
    with pytest.raises(GitError, match="clean"):
        WorktreeManager(baseline_repo, tmp_path / "worktrees").create_worktree(
            uuid4(), git(baseline_repo, "rev-parse", "HEAD").strip()
        )


def test_cleanup_refuses_unmanaged_or_unregistered(baseline_repo: Path, tmp_path: Path) -> None:
    manager = WorktreeManager(baseline_repo, tmp_path / "worktrees")
    victim = tmp_path / "user-data"
    victim.mkdir()
    for target in (baseline_repo, victim, tmp_path / "worktrees" / str(uuid4())):
        with pytest.raises(GitError):
            manager.cleanup_worktree(target)
    assert victim.exists() and baseline_repo.exists()


def test_cleanup_refuses_symlink(baseline_repo: Path, tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    root.mkdir()
    link = root / str(uuid4())
    link.symlink_to(baseline_repo)
    with pytest.raises(GitError):
        WorktreeManager(baseline_repo, root).cleanup_worktree(link)
    assert baseline_repo.exists()


def test_rejects_existing_worktree_and_internal_root(baseline_repo: Path, tmp_path: Path) -> None:
    manager = WorktreeManager(baseline_repo, tmp_path / "worktrees")
    identity, sha = uuid4(), manager.get_head_sha()
    worktree = manager.create_worktree(identity, sha)
    with pytest.raises(GitError, match="already exists"):
        manager.create_worktree(identity, sha)
    manager.cleanup_worktree(worktree)
    with pytest.raises(GitError, match="outside"):
        WorktreeManager(baseline_repo, baseline_repo / "runtime")
