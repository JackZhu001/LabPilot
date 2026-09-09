"""Every test runs offline, without credentials or telemetry."""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

from labpilot.persistence.repository import SQLiteResearchRepository


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    for name in ("OPENAI_API_KEY", "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture()
def repository(tmp_path: Path) -> Iterator[SQLiteResearchRepository]:
    store = SQLiteResearchRepository(tmp_path / "research.sqlite3")
    yield store
    store.close()
