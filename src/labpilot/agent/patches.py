"""Policy and disposable-worktree validation for model-proposed unified diffs."""

from __future__ import annotations

from pathlib import PurePosixPath
from uuid import uuid4

from labpilot.execution.git import GitError, WorktreeManager
from labpilot.llm.models import PatchProposal

DENIED_PARTS = {".git", ".labpilot", "outputs", "datasets", "data", "logs"}
DENIED_NAMES = {".env", ".env.example", "credentials.json", "secrets.json"}
DESTRUCTIVE_TOKENS = ("rm -rf", "curl |", "wget |", "os.system(", "shell=true")


class PatchPolicyError(ValueError):
    pass


class PatchValidator:
    def __init__(self, manager: WorktreeManager, *, max_bytes: int = 100_000) -> None:
        self.manager = manager
        self.max_bytes = max_bytes

    @staticmethod
    def target_paths(diff: str) -> tuple[str, ...]:
        paths: list[str] = []
        for line in diff.splitlines():
            if not line.startswith("+++ "):
                continue
            name = line[4:].split("\t", 1)[0]
            if name == "/dev/null":
                continue
            if not name.startswith("b/"):
                raise PatchPolicyError("Patch target must use a b/ prefix")
            paths.append(name[2:])
        return tuple(dict.fromkeys(paths))

    def validate(
        self, proposal: PatchProposal, *, expected_sha: str, allowed_targets: tuple[str, ...]
    ) -> str:
        diff = proposal.unified_diff
        if diff and not diff.endswith("\n"):
            diff += "\n"
        if proposal.base_commit_sha != expected_sha:
            raise PatchPolicyError("Patch base SHA does not match the plan")
        if len(diff.encode()) > self.max_bytes:
            raise PatchPolicyError("Patch exceeds the size limit")
        try:
            WorktreeManager.validate_patch(diff)
        except GitError as exc:
            raise PatchPolicyError(str(exc)) from exc
        targets = self.target_paths(diff)
        if not targets or len(targets) > 6 or set(targets) != set(proposal.target_files):
            raise PatchPolicyError("Patch headers and declared targets differ")
        if not set(targets) <= set(allowed_targets):
            raise PatchPolicyError("Patch modifies a file outside the approved plan")
        for name in targets:
            relative = PurePosixPath(name)
            lowered = {part.lower() for part in relative.parts}
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or lowered.intersection(DENIED_PARTS)
                or relative.name.lower() in DENIED_NAMES
                or relative.name.lower().startswith(".env")
            ):
                raise PatchPolicyError("Patch contains an unsafe target path")
        added = "\n".join(
            line[1:].lower()
            for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        if any(token in added for token in DESTRUCTIVE_TOKENS):
            raise PatchPolicyError("Patch introduces disallowed command execution")

        identity = uuid4()
        worktree = self.manager.create_worktree(identity, expected_sha)
        try:
            self.manager.apply_patch(worktree, diff, expected_sha)
            actual = self.manager.get_diff(worktree)
            for name in targets:
                target = worktree / name
                if target.suffix == ".py" and target.is_file():
                    compile(target.read_text(), str(target), "exec")
            return actual
        except (GitError, OSError, SyntaxError) as exc:
            raise PatchPolicyError(str(exc)) from exc
        finally:
            self.manager.cleanup_worktree(worktree)
