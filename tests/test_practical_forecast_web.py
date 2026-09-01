import re
from datetime import date, datetime

import pytest

from workhours.web import create_app


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        database_path=tmp_path / "workhours.sqlite3",
        today_provider=lambda: date(2026, 7, 6),
        now_provider=lambda: datetime(2026, 7, 6, 9),
    )
    application.config.update(TESTING=True)
    return application


def _seed_one_hour_balance(client) -> None:
    client.post(
        "/entries",
        data={
            "work_date": "2026-07-03",
            "start_time": "08:00",
            "end_time": "19:30",
        },
    )


def test_selected_date_focuses_the_earliest_clock_out_and_keeps_editing_visible(app):
    client = app.test_client()
    _seed_one_hour_balance(client)
    client.post(
        "/entries",
        data={
            "work_date": "2026-07-06",
            "start_time": "08:00",
            "end_time": "",
        },
    )

    response = client.get("/?reference_date=2026-07-06")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    focus = re.search(
        r'<section[^>]*id="selected-forecast"[^>]*>(.*?)</section>',
        body,
        re.DOTALL,
    )
    assert focus is not None
    assert "最早可下班" in focus.group(1)
    assert "17:30" in focus.group(1)
    assert "带入余额" in focus.group(1)
    assert "+1小时" in focus.group(1)
    assert "今日需工作" in focus.group(1)
    assert "8小时" in focus.group(1)
    assert "余额抵扣1小时" in focus.group(1)
    assert body.index('id="selected-entry"') < body.index(
        '<details class="advanced-settings">'
    )
    assert re.search(
        r'<details class="advanced-settings">\s*<summary',
        body,
    )


def test_preview_endpoint_recalculates_without_saving(app):
    client = app.test_client()
    _seed_one_hour_balance(client)

    response = client.get(
        "/preview/earliest-end?work_date=2026-07-06&start_time=08:00"
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "available": True,
        "balance_before_minutes": 60,
        "balance_label": "+1小时",
        "day_offset": 0,
        "reason_label": "余额抵扣1小时",
        "required_label": "8小时",
        "required_minutes": 480,
        "suggested_end": "17:30",
        "suggested_end_label": "17:30",
    }
    assert client.application.extensions["workhours_store"].get_entry(
        date(2026, 7, 6)
    ) is None


def test_preview_endpoint_rejects_invalid_input(app):
    response = app.test_client().get(
        "/preview/earliest-end?work_date=2026-07-06&start_time=invalid"
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "日期或上班时间无效"}


def test_prediction_table_has_mobile_card_controls_and_selected_row_marker(app):
    response = app.test_client().get("/?reference_date=2026-07-06")
    body = response.get_data(as_text=True)

    assert 'id="toggle-other-days"' in body
    assert 'class="prediction-table"' in body
    selected = re.search(
        r'<tr(?P<attributes>[^>]*)data-work-date="2026-07-06"[^>]*>',
        body,
    )
    other = re.search(
        r'<tr(?P<attributes>[^>]*)data-work-date="2026-07-07"[^>]*>',
        body,
    )
    assert selected is not None
    assert "is-selected-day" in selected.group("attributes")
    assert other is not None
    assert "other-day" in other.group("attributes")
    assert 'data-label="最早下班时间"' in body
