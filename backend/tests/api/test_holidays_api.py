from fastapi.testclient import TestClient

from backend.services.holidays import HolidayResult


def test_holiday_endpoint_contract(client: TestClient, monkeypatch) -> None:
    async def fake_get_holidays(conn, year, client=None):
        return HolidayResult(
            year,
            {"01-01": {"name": "元旦", "isOffDay": True}},
            "cache",
        )

    monkeypatch.setattr("backend.api.holidays.get_holidays", fake_get_holidays)
    response = client.get("/api/holidays/2026")
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "holidays": {"01-01": {"name": "元旦", "isOffDay": True}},
        "source": "cache",
    }
