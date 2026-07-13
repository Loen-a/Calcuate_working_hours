from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app


def test_root_serves_built_single_file(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "dist"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text(
        "<!doctype html><title>Workhours</title>",
        encoding="utf-8",
    )
    app = create_app(tmp_path / "test.db", frontend_dir=frontend_dir)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Workhours" in response.text


def test_missing_build_returns_clear_503(tmp_path: Path) -> None:
    app = create_app(
        tmp_path / "test.db",
        frontend_dir=tmp_path / "missing-dist",
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "frontend build not found; run npm --prefix frontend run build"
    }
