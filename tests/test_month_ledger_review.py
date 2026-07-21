from datetime import date, time

from workhours.domain import ForecastSettings, PeriodMode, WorkEntry, build_forecast
from workhours.web import create_app


def test_summary_calls_remaining_target_a_ledger_gap(tmp_path):
    app = create_app(
        database_path=tmp_path / "workhours.sqlite3",
        today_provider=lambda: date(2026, 7, 13),
    )
    app.config.update(TESTING=True)

    response = app.test_client().get("/?reference_date=2026-07-13")

    body = response.get_data(as_text=True)
    assert "当前账面缺口" in body
    assert "当前建议剩余" not in body


def test_past_partial_entry_is_missing_and_neutral_for_planning():
    partial_entry = WorkEntry(
        work_date=date(2026, 7, 10),
        start=time(9),
        end=None,
    )

    forecast = build_forecast(
        reference_date=date(2026, 7, 13),
        entries={partial_entry.work_date: partial_entry},
        overrides={},
        settings=ForecastSettings(period=PeriodMode.MONTH),
    )

    assert date(2026, 7, 10) in forecast.missing_history_days
    assert forecast.remaining_target_minutes == 15 * 9 * 60
    assert forecast.days[date(2026, 7, 10)].reason == "missing_entry"
    assert forecast.days[date(2026, 7, 13)].recommended_minutes == 9 * 60
