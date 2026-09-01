from datetime import date, datetime

import pytest

from workhours.web import create_app


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        database_path=tmp_path / "workhours.sqlite3",
        today_provider=lambda: date(2026, 7, 6),
        now_provider=lambda: datetime(2026, 7, 6, 9, 30),
    )
    application.config.update(TESTING=True)
    return application


def test_dashboard_loads(app):
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "工作时长预测" in response.get_data(as_text=True)
    assert "周平均" in response.get_data(as_text=True)


def test_settings_can_switch_to_month_mode(app):
    response = app.test_client().post(
        "/settings",
        data={"period": "month"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "月平均" in response.get_data(as_text=True)


def test_calendar_override_can_be_created(app):
    client = app.test_client()
    client.post("/settings", data={"period": "month"}, follow_redirects=True)

    response = client.post(
        "/calendar",
        data={"work_date": "2026-07-04", "kind": "workday"},
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "2026-07-04" in body
    assert "调休上班" in body


def test_work_entry_can_be_created(app):
    response = app.test_client().post(
        "/entries",
        data={
            "work_date": "2026-07-06",
            "start_time": "09:30",
            "end_time": "20:00",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "09:30" in body
    assert "20:00" in body
    assert "8小时30分钟" in body


def test_dashboard_can_focus_an_arbitrary_reference_date(app):
    response = app.test_client().get("/?reference_date=2026-07-01")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "2026-07-01 至 2026-07-05" in body
    assert 'name="reference_date"' in body
    assert 'value="2026-07-01"' in body


def test_past_entry_save_redirects_to_saved_date_period(app):
    response = app.test_client().post(
        "/entries",
        data={
            "work_date": "2026-07-01",
            "start_time": "09:30",
            "end_time": "20:00",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "2026-07-01 至 2026-07-05" in body
    assert 'value="2026-07-01"' in body
    assert "09:30" in body
    assert "20:00" in body
    assert "8小时30分钟" in body


def test_existing_past_entry_can_be_updated_and_recalculated(app):
    client = app.test_client()
    client.post(
        "/entries",
        data={
            "work_date": "2026-07-01",
            "start_time": "09:00",
            "end_time": "18:30",
        },
        follow_redirects=True,
    )

    response = client.post(
        "/entries",
        data={
            "work_date": "2026-07-01",
            "start_time": "09:00",
            "end_time": "20:30",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "9小时30分钟" in body
    assert "17小时30分钟" in body


def test_prediction_table_exposes_inline_entry_editing(app):
    response = app.test_client().get("/?reference_date=2026-07-01")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "entry-form-2026-07-01" in body
    assert 'form="entry-form-2026-07-01"' in body
    assert "<th>操作</th>" in body


@pytest.mark.parametrize(
    ("return_target", "expected_anchor"),
    (
        ("selected_entry", "selected-entry"),
        ("prediction", "prediction-2026-07-06"),
    ),
)
def test_entry_save_returns_to_the_originating_record(
    app,
    return_target: str,
    expected_anchor: str,
):
    response = app.test_client().post(
        "/entries",
        data={
            "work_date": "2026-07-06",
            "start_time": "08:00",
            "end_time": "",
            "return_target": return_target,
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"?reference_date=2026-07-06#{expected_anchor}"
    )
