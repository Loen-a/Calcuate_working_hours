import sqlite3
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db


def test_health_entries_and_preferences(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/entries").json() == {}
    assert client.get("/api/preferences").json() == {"theme": "cool"}

    saved = client.put(
        "/api/entries/2026-07-12",
        json={"in": "08:00", "out": "18:30", "counts": True},
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "date": "2026-07-12",
        "entry": {"in": "08:00", "out": "18:30", "counts": True},
    }
    assert client.get("/api/entries").json() == {
        "2026-07-12": {"in": "08:00", "out": "18:30", "counts": True}
    }

    assert client.put("/api/preferences", json={"theme": "teal"}).json() == {
        "theme": "teal"
    }
    assert client.get("/api/preferences").json() == {"theme": "teal"}
    assert client.delete("/api/entries/2026-07-12").status_code == 204
    assert client.get("/api/entries").json() == {}
    assert client.delete("/api/entries/2026-07-12").status_code == 404


@pytest.mark.parametrize(
    ("work_date", "payload"),
    [
        ("not-a-date", {"in": "08:00", "out": "18:00"}),
        ("20260712", {"in": "08:00", "out": "18:00"}),
        ("2026-07-12", {"in": "8:00", "out": "18:00"}),
        ("2026-07-12", {"in": "08:00", "out": "24:00"}),
        ("2026-07-12", {"in": "18:00", "out": "08:00"}),
        ("2026-07-12", {"in": "08:00", "out": "08:00"}),
    ],
)
def test_invalid_entry_is_rejected(
    client: TestClient,
    work_date: str,
    payload: dict[str, str],
) -> None:
    response = client.put(f"/api/entries/{work_date}", json=payload)
    assert response.status_code == 422


def test_entry_without_counts_preserves_exact_json_aliases(
    client: TestClient,
) -> None:
    response = client.put(
        "/api/entries/2026-07-12",
        json={"in": "08:00", "out": "18:30"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "date": "2026-07-12",
        "entry": {"in": "08:00", "out": "18:30"},
    }
    assert client.get("/api/entries").json() == {
        "2026-07-12": {"in": "08:00", "out": "18:30"}
    }


def test_sqlite_errors_are_mapped_to_safe_response(client: TestClient) -> None:
    def broken_db() -> Iterator[sqlite3.Connection]:
        raise sqlite3.OperationalError("sensitive database detail")
        yield

    client.app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/api/health")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {"detail": "database operation failed"}
    assert "sensitive database detail" not in response.text
