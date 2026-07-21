from datetime import date, datetime

import pytest

from workhours.web import create_app


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        database_path=tmp_path / "workhours.sqlite3",
        today_provider=lambda: date(2026, 7, 13),
        now_provider=lambda: datetime(2026, 7, 13, 9, 30),
    )
    application.config.update(TESTING=True)
    return application


def test_weekly_dashboard_uses_month_ledger_but_displays_current_week(app):
    client = app.test_client()
    for day in (1, 2, 3, 6, 7, 8, 9, 10):
        client.post(
            "/entries",
            data={
                "work_date": f"2026-07-{day:02d}",
                "start_time": "09:00",
                "end_time": "18:30",
            },
        )

    response = client.get("/?reference_date=2026-07-13")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'data-month-target-minutes="12420"' in body
    assert 'data-carryover-minutes="480"' in body
    assert "entry-form-2026-07-13" in body
    assert "entry-form-2026-07-10" not in body
    assert "10小时36分钟" in body


def test_dashboard_warns_when_month_history_is_incomplete(app):
    response = app.test_client().get("/?reference_date=2026-07-13")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="missing-history-warning"' in body
    assert 'data-missing-count="8"' in body
    assert "暂按9小时" in body


def test_cross_month_week_is_clipped_to_selected_month(app):
    response = app.test_client().get("/?reference_date=2026-07-01")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "2026-07-01" in body
    assert "2026-07-05" in body
    assert "entry-form-2026-06-29" not in body
