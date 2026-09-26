"""Deterministic, bounded repository context selection with secret exclusion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labpilot.execution.git import git
from labpilot.llm.models import InspectedFile

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "datasets",
    "data",
    "outputs",
    "logs",
    ".labpilot",
    "__pycache__",
}
SECRET_NAMES = {
    ".env",
    ".env.example",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}
TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".md", ".txt", ".json"}
PRIORITY_NAMES = {
    "readme.md": 0,
    "train.py": 1,
    "model.py": 2,
    "config.yaml": 3,
    "config.yml": 3,
    "dataset.json": 4,
    "pyproject.toml": 5,
    "requirements.txt": 6,
}


@dataclass(frozen=True)
class RepositoryContext:
    repo_path: Path
    base_commit_sha: str
    file_tree: tuple[str, ...]
    important_files: tuple[InspectedFile, ...]
    content: str


class RepositoryInspector:
    def __init__(
        self, *, max_context_characters: int = 60_000, max_file_bytes: int = 30_000
    ) -> None:
        self.max_context_characters = max_context_characters
        self.max_file_bytes = max_file_bytes

    @staticmethod
    def safe_path(name: str) -> bool:
        path = Path(name)
        lowered = {part.lower() for part in path.parts}
        filename = path.name.lower()
        return (
            not path.is_absolute()
            and ".." not in path.parts
            and not lowered.intersection(EXCLUDED_PARTS)
            and filename not in SECRET_NAMES
            and not filename.startswith(".env")
            and not any(token in filename for token in ("secret", "credential", "api_key"))
        )

    def inspect(self, repo: Path, expected_sha: str) -> RepositoryContext:
        repo = repo.resolve()
        actual = git(repo, "rev-parse", "HEAD").strip()
        if actual != expected_sha:
            raise ValueError("Repository HEAD differs from configured base commit")
        tracked = tuple(item for item in git(repo, "ls-files", "-z").split("\0") if item)
        safe = tuple(name for name in tracked if self.safe_path(name))
        tree = safe[:256]
        candidates = sorted(
            (
                name
                for name in safe
                if Path(name).suffix.lower() in TEXT_SUFFIXES
                and (repo / name).is_file()
                and not (repo / name).is_symlink()
            ),
            key=lambda name: (PRIORITY_NAMES.get(Path(name).name.lower(), 20), name),
        )
        chunks: list[str] = []
        selected: list[InspectedFile] = []
        used = 0
        for name in candidates:
            path = repo / name
            size = path.stat().st_size
            if size > self.max_file_bytes:
                continue
            try:
                value = path.read_text()
            except UnicodeDecodeError:
                continue
            chunk = f"\n--- FILE {name} ---\n{value}"
            if used + len(chunk) > self.max_context_characters:
                continue
            chunks.append(chunk)
            selected.append(InspectedFile(path=name, size_bytes=size))
            used += len(chunk)
            if len(selected) == 32:
                break
        if not selected:
            raise ValueError("No safe text files were available for repository inspection")
        return RepositoryContext(repo, actual, tree, tuple(selected), "".join(chunks))

    def read_selected(self, repo: Path, names: tuple[str, ...]) -> str:
        chunks: list[str] = []
        used = 0
        for name in names:
            if not self.safe_path(name):
                raise ValueError("Unsafe selected repository path")
            path = repo.resolve() / name
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(repo.resolve())
                or not path.is_file()
                or path.stat().st_size > self.max_file_bytes
            ):
                raise ValueError("Selected repository file is unavailable or too large")
            value = path.read_text()
            chunk = f"\n--- FILE {name} ---\n{value}"
            if used + len(chunk) > self.max_context_characters:
                raise ValueError("Selected repository context exceeds its limit")
            chunks.append(chunk)
            used += len(chunk)
        return "".join(chunks)
