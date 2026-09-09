"""Managed detached worktrees; experiment edits never target the baseline checkout."""

import subprocess
from pathlib import Path, PurePosixPath
from uuid import UUID


class GitError(RuntimeError):
    def __init__(self, operation: str, detail: str) -> None:
        self.operation = operation
        self.detail = detail
        super().__init__(f"Git {operation}: {detail}")


def git(repo: Path, *arguments: str, input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *arguments],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(arguments[0], str(exc)) from exc
    if result.returncode:
        raise GitError(arguments[0], result.stderr.strip() or result.stdout.strip())
    return result.stdout


class WorktreeManager:
    """Only UUID children registered to this baseline are eligible for removal."""

    def __init__(self, baseline: Path, root: Path) -> None:
        self.baseline = baseline.resolve()
        self.root = root.resolve()
        if self.root.is_relative_to(self.baseline):
            raise GitError("configure", "Managed root must be outside the baseline")

    def get_head_sha(self, path: Path | None = None) -> str:
        return git(path or self.baseline, "rev-parse", "HEAD").strip()

    def validate_clean_baseline(self, expected_sha: str | None = None) -> str:
        top = Path(git(self.baseline, "rev-parse", "--show-toplevel").strip()).resolve()
        if top != self.baseline:
            raise GitError("validate", "Use the root of a dedicated baseline Git repository")
        if git(self.baseline, "status", "--porcelain", "--untracked-files=all").strip():
            raise GitError("validate", "Baseline repository must be clean")
        sha = self.get_head_sha()
        if expected_sha is not None and sha != expected_sha:
            raise GitError("validate", "Baseline HEAD differs from the recorded base commit")
        return sha

    def _managed(self, path: Path, registered: bool = True) -> Path:
        if path.is_symlink() or path.resolve().parent != self.root:
            raise GitError("validate", "Target is not a direct managed worktree")
        try:
            UUID(path.name)
        except ValueError as exc:
            raise GitError("validate", "Worktree identity must be a UUID") from exc
        if registered:
            known = git(self.baseline, "worktree", "list", "--porcelain").splitlines()
            if f"worktree {path.resolve()}" not in known:
                raise GitError("validate", "Target is not registered to the baseline")
        return path.resolve()

    def create_worktree(self, experiment_id: UUID, expected_sha: str) -> Path:
        self.validate_clean_baseline(expected_sha)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._managed(self.root / str(experiment_id), registered=False)
        if path.exists():
            raise GitError("create", "Worktree already exists; reconcile the interrupted execution")
        git(self.baseline, "worktree", "add", "--detach", str(path), expected_sha)
        return path

    @staticmethod
    def validate_patch(diff: str) -> None:
        if not diff.strip() or "\x00" in diff:
            raise GitError("patch", "Expected a nonempty unified diff")
        headers = [line for line in diff.splitlines() if line.startswith(("--- ", "+++ "))]
        if not headers or not any(line.startswith("@@ ") for line in diff.splitlines()):
            raise GitError("patch", "Only text unified diffs are supported")
        if any(token in diff for token in ("120000", "160000", "GIT binary patch")):
            raise GitError("patch", "Symlinks, submodules and binary patches are unsupported")
        for header in headers:
            name = header[4:].split("\t", 1)[0]
            if name == "/dev/null":
                continue
            if not name.startswith(("a/", "b/")):
                raise GitError("patch", "Patch paths must use a/ and b/ prefixes")
            parts = PurePosixPath(name[2:]).parts
            if not parts or any(part in {"..", "/", ".git", "outputs"} for part in parts):
                raise GitError("patch", "Unsafe patch path")

    def apply_patch(self, path: Path, diff: str, expected_sha: str) -> None:
        path = self._managed(path)
        if self.get_head_sha(path) != expected_sha:
            raise GitError("patch", "Patch base commit does not match worktree")
        self.validate_patch(diff)
        git(path, "apply", "--check", "--index", "-", input_text=diff)
        git(path, "apply", "--index", "-", input_text=diff)

    def get_diff(self, path: Path) -> str:
        return git(self._managed(path), "diff", "HEAD", "--binary", "--no-ext-diff")

    def tracked_files(self, path: Path) -> tuple[str, ...]:
        return tuple(
            name for name in git(self._managed(path), "ls-files", "-z").split("\0") if name
        )

    def cleanup_worktree(self, path: Path) -> None:
        git(self.baseline, "worktree", "remove", "--force", str(self._managed(path)))
