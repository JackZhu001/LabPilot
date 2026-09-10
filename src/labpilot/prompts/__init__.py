"""Versioned prompt templates for bounded logical agent roles."""

from pathlib import Path


def load_prompt(name: str) -> str:
    if not name.isidentifier():
        raise ValueError("Invalid prompt name")
    return (Path(__file__).parent / f"{name}.md").read_text()
