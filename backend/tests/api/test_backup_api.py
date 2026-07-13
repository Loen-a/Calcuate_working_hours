import json
import re

from fastapi.testclient import TestClient


def test_backup_download_and_legacy_upload(client: TestClient) -> None:
    download = client.get("/api/backup")
    assert download.status_code == 200
    assert download.json()["version"] == 2
    disposition = download.headers["content-disposition"]
    assert re.fullmatch(
        r'attachment; filename="workhours-\d{4}-\d{2}-\d{2}'
        r'-\d{2}-\d{2}-\d{2}\.json"',
        disposition,
    )

    legacy = {
        "version": 1,
        "exportedAt": "2026-07-12T00:00:00Z",
        "entries": {
            "2026-07-12": {"in": "08:00", "out": "18:30"}
        },
    }
    upload = client.post(
        "/api/backup",
        files={
            "file": (
                "legacy.json",
                json.dumps(legacy).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert upload.status_code == 200
    assert upload.json()["entries"] == 1


def test_invalid_backup_upload_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/backup",
        files={"file": ("bad.json", b"not json", "application/json")},
    )

    assert response.status_code == 400
