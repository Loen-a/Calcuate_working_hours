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


def test_dashboard_lists_default_non_working_intervals(app):
    response = app.test_client().get("/")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "非工作时间" in body
    assert "午休" in body
    assert "12:00" in body
    assert "13:30" in body
    assert "晚间休息" in body
    assert "19:30" in body
    assert "20:00" in body
    assert "2 条启用规则" in body


def test_interval_can_be_created_updated_disabled_and_deleted(app):
    client = app.test_client()

    created_response = client.post(
        "/non-working-intervals",
        data={
            "name": "下午休息",
            "start_time": "15:00",
            "end_time": "15:15",
            "enabled": "1",
            "reference_date": "2026-07-06",
        },
        follow_redirects=True,
    )
    created_body = created_response.get_data(as_text=True)
    assert created_response.status_code == 200
    assert "下午休息" in created_body
    assert 'data-interval-id="3"' in created_body
    assert 'data-enabled="true"' in created_body

    updated_response = client.post(
        "/non-working-intervals",
        data={
            "interval_id": "3",
            "name": "下午茶",
            "start_time": "15:10",
            "end_time": "15:30",
            "reference_date": "2026-07-06",
        },
        follow_redirects=True,
    )
    updated_body = updated_response.get_data(as_text=True)
    assert updated_response.status_code == 200
    assert "下午茶" in updated_body
    assert 'data-enabled="false"' in updated_body

    deleted_response = client.post(
        "/non-working-intervals/delete",
        data={"interval_id": "3", "reference_date": "2026-07-06"},
        follow_redirects=True,
    )
    assert deleted_response.status_code == 200
    assert "下午茶" not in deleted_response.get_data(as_text=True)


@pytest.mark.parametrize(
    "data",
    [
        {"name": "", "start_time": "12:00", "end_time": "13:00"},
        {"name": "无效", "start_time": "13:00", "end_time": "13:00"},
        {"name": "无效", "start_time": "14:00", "end_time": "13:00"},
    ],
)
def test_invalid_interval_shows_error(app, data):
    response = app.test_client().post(
        "/non-working-intervals",
        data={**data, "reference_date": "2026-07-06"},
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "名称不能为空，且开始时间必须早于结束时间" in body


def test_rule_change_recalculates_existing_entries(app):
    client = app.test_client()
    initial_response = client.post(
        "/entries",
        data={
            "work_date": "2026-07-06",
            "start_time": "09:00",
            "end_time": "20:30",
        },
        follow_redirects=True,
    )
    assert "9小时30分钟" in initial_response.get_data(as_text=True)

    recalculated_response = client.post(
        "/non-working-intervals",
        data={
            "interval_id": "2",
            "name": "晚间休息",
            "start_time": "19:30",
            "end_time": "20:00",
            "reference_date": "2026-07-06",
        },
        follow_redirects=True,
    )

    recalculated_body = recalculated_response.get_data(as_text=True)
    assert recalculated_response.status_code == 200
    assert "10小时" in recalculated_body
    assert "1 条启用规则" in recalculated_body
