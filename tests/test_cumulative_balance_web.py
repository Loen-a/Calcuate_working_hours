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


def _table_row(body: str, work_date: str) -> str:
    match = re.search(
        rf'<tr data-work-date="{re.escape(work_date)}">(.*?)</tr>',
        body,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def _earliest_end_cell(row: str) -> str:
    match = re.search(
        r'<td class="earliest-end-cell">(.*?)</td>',
        row,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_table_shows_balance_adjusted_earliest_end_in_24_hour_time(app):
    client = app.test_client()
    client.post(
        "/settings",
        data={"period": "month", "reference_date": "2026-07-06"},
    )
    client.post(
        "/entries",
        data={
            "work_date": "2026-07-03",
            "start_time": "08:00",
            "end_time": "19:30",
        },
    )
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
    current_row = _table_row(body, "2026-07-06")

    assert response.status_code == 200
    assert "<th>最早下班时间</th>" in body
    assert "<th>建议工时</th>" not in body
    assert "17:30" in _earliest_end_cell(current_row)


def test_earliest_end_is_empty_without_a_start_time(app):
    response = app.test_client().get("/?reference_date=2026-07-06")

    row = _table_row(response.get_data(as_text=True), "2026-07-06")
    assert _earliest_end_cell(row).strip() == "-"


def test_table_replaces_suggested_end_with_monthly_balance(app):
    client = app.test_client()
    client.post(
        "/settings",
        data={"period": "month", "reference_date": "2026-07-06"},
    )
    entries = [
        ("2026-07-01", "20:10"),  # 9h10m effective, +10m
        ("2026-07-02", "18:50"),  # 8h20m effective, -40m
        ("2026-07-03", "19:30"),  # 9h effective, 0m
        ("2026-07-06", "20:30"),  # 9h30m effective, +30m
    ]
    for work_date, end_time in entries:
        client.post(
            "/entries",
            data={
                "work_date": work_date,
                "start_time": "09:00",
                "end_time": end_time,
            },
        )

    response = client.get("/?reference_date=2026-07-06")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<th>累计余额</th>" in body
    assert "<th>建议下班</th>" not in body

    july_1 = _table_row(body, "2026-07-01")
    assert 'data-daily-balance-minutes="10"' in july_1
    assert 'data-cumulative-balance-minutes="10"' in july_1
    assert "balance-value positive" in july_1
    assert "+10分钟" in july_1
    assert "当日 +10分钟" in july_1

    july_2 = _table_row(body, "2026-07-02")
    assert 'data-daily-balance-minutes="-40"' in july_2
    assert 'data-cumulative-balance-minutes="-30"' in july_2
    assert "balance-value negative" in july_2
    assert "-30分钟" in july_2
    assert "当日 -40分钟" in july_2

    july_3 = _table_row(body, "2026-07-03")
    assert 'data-daily-balance-minutes="0"' in july_3
    assert 'data-cumulative-balance-minutes="-30"' in july_3
    assert "当日 0分钟" in july_3

    july_6 = _table_row(body, "2026-07-06")
    assert 'data-daily-balance-minutes="30"' in july_6
    assert 'data-cumulative-balance-minutes="0"' in july_6
    assert "balance-value neutral" in july_6
    assert "0分钟" in july_6
    assert "当日 +30分钟" in july_6


def test_incomplete_day_has_no_balance_value(app):
    response = app.test_client().get("/?reference_date=2026-07-06")

    row = _table_row(response.get_data(as_text=True), "2026-07-06")
    assert 'data-daily-balance-minutes=""' in row
    assert 'data-cumulative-balance-minutes=""' in row
    assert '<span class="balance-empty">-</span>' in row
