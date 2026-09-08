from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time
from pathlib import Path
from typing import Callable

from flask import Flask, current_app, flash, jsonify, make_response, redirect, render_template, request, send_file, url_for

from workhours.domain import (
    DayForecast,
    DayOverride,
    Forecast,
    ForecastSettings,
    NonWorkingInterval,
    PeriodMode,
    WorkEntry,
    build_forecast,
    period_bounds,
)
from workhours.storage import WorkHoursStore, default_database_path
from workhours.holidays import HolidayResult, get_holidays


TodayProvider = Callable[[], date]
NowProvider = Callable[[], datetime]


def create_app(
    database_path: str | Path | None = None,
    today_provider: TodayProvider | None = None,
    now_provider: NowProvider | None = None,
) -> Flask:
    app = Flask(__name__)
    app.secret_key = "local-workhours-dev"
    app.config.update(DEFAULT_INTERFACE="new", HOLIDAY_NETWORK_ENABLED=True,
                      MAX_CONTENT_LENGTH=16 * 1024 * 1024)

    today_provider = today_provider or date.today
    now_provider = now_provider or datetime.now
    store = WorkHoursStore(database_path or default_database_path())
    app.extensions["workhours_store"] = store

    @app.get("/")
    def index():
        explicit_interface = request.args.get("ui")
        interface = explicit_interface or request.cookies.get("workhours_ui") or app.config["DEFAULT_INTERFACE"]
        if interface == "new":
            modern = Path(app.static_folder) / "modern" / "index.html"
            if not modern.is_file():
                return '新界面资源尚未准备好。<a href="/?ui=old">打开旧界面</a>', 503
            response = send_file(modern, max_age=0)
        else:
            today = today_provider()
            selected_date = _selected_date(today)
            dashboard = _build_dashboard(store, today, selected_date)
            response = make_response(render_template("index.html", **dashboard))
        if explicit_interface in {"old", "new"}:
            response.set_cookie("workhours_ui", explicit_interface, max_age=365 * 24 * 60 * 60,
                                httponly=True, samesite="Lax")
        return response

    @app.get("/interface/<interface>")
    def switch_interface(interface):
        if interface not in {"new", "old"}:
            return "未知界面", 404
        selected_date = _selected_date(today_provider())
        response = _redirect_to_reference(selected_date)
        response.set_cookie("workhours_ui", interface, max_age=365 * 24 * 60 * 60,
                            httponly=True, samesite="Lax")
        return response

    @app.get("/preview/earliest-end")
    def preview_earliest_end():
        try:
            work_date = _parse_required_date(request.args.get("work_date"))
            start = _parse_time(request.args.get("start_time"))
            if start is None:
                raise ValueError("Start time is required")
        except (TypeError, ValueError):
            return jsonify({"error": "日期或上班时间无效"}), 400

        settings = store.get_settings()
        month_start, month_end = period_bounds(work_date, PeriodMode.MONTH)
        overrides, _ = _effective_calendar(store, month_start, month_end)
        entries = store.list_entries(month_start, month_end)
        preview = _preview_day_forecast(
            work_date,
            start,
            entries,
            overrides,
            settings,
            store.list_leave_days(month_start, month_end),
        )
        return jsonify(_preview_payload(preview, settings))

    @app.post("/leaves")
    def save_leave():
        work_date = _parse_required_date(request.form.get("work_date"))
        enabled = request.form.get("enabled") == "1"
        store.set_leave(work_date, enabled)
        flash("已标记全天请假，原打卡记录已保留" if enabled else "已取消请假，工时已重新计算", "success")
        return _redirect_to_reference(work_date)

    @app.post("/holidays/refresh")
    def refresh_holidays():
        selected_date = _parse_date(request.form.get("reference_date")) or today_provider()
        result = _holiday_result(store, selected_date.year, refresh=True)
        flash(result.warning or "节假日已刷新，工时已重新计算", "error" if result.warning else "success")
        return _redirect_to_reference(selected_date)

    @app.post("/settings")
    def update_settings():
        period = PeriodMode(request.form["period"])
        reference_date = _parse_date(request.form.get("reference_date")) or today_provider()
        store.set_period(period)
        flash("统计周期已更新", "success")
        return _redirect_to_reference(reference_date)

    @app.post("/entries")
    def save_entry():
        work_date = _parse_required_date(request.form.get("work_date"))
        entry = WorkEntry(
            work_date=work_date,
            start=_parse_time(request.form.get("start_time")),
            end=_parse_time(request.form.get("end_time")),
            lunch_minutes=90,
        )
        store.save_entry(entry)
        flash("工时记录已保存", "success")
        anchor = _entry_return_anchor(
            request.form.get("return_target"),
            work_date,
        )
        return _redirect_to_reference(work_date, anchor)

    @app.post("/clock-in")
    def clock_in():
        now = now_provider()
        _record_clock(store, now, start=True)
        flash("已记录上班时间", "success")
        return _redirect_to_reference(now.date())

    @app.post("/clock-out")
    def clock_out():
        now = now_provider()
        _record_clock(store, now, start=False)
        flash("已记录下班时间", "success")
        return _redirect_to_reference(now.date())

    @app.post("/calendar")
    def save_calendar_override():
        work_date = _parse_required_date(request.form.get("work_date"))
        override = DayOverride(request.form["kind"])
        store.set_override(work_date, override)
        flash("日历标记已保存", "success")
        return _redirect_to_reference(work_date)

    @app.post("/calendar/delete")
    def delete_calendar_override():
        work_date = _parse_required_date(request.form.get("work_date"))
        store.delete_override(work_date)
        flash("日历标记已删除", "success")
        return _redirect_to_reference(work_date)

    @app.post("/non-working-intervals")
    def save_non_working_interval():
        reference_date = (
            _parse_date(request.form.get("reference_date")) or today_provider()
        )
        try:
            start = _parse_time(request.form.get("start_time"))
            end = _parse_time(request.form.get("end_time"))
            if start is None or end is None:
                raise ValueError("Interval times are required.")

            interval = NonWorkingInterval(
                interval_id=_parse_interval_id(request.form.get("interval_id")),
                name=request.form.get("name", ""),
                start=start,
                end=end,
                enabled=request.form.get("enabled") == "1",
            )
            store.save_non_working_interval(interval)
        except ValueError:
            flash(
                "保存失败：名称不能为空，且开始时间必须早于结束时间。",
                "error",
            )
        else:
            flash("非工作时间已保存，工时已自动重算。", "success")
        return _redirect_to_reference(reference_date)

    @app.post("/non-working-intervals/delete")
    def delete_non_working_interval():
        reference_date = (
            _parse_date(request.form.get("reference_date")) or today_provider()
        )
        try:
            interval_id = _parse_interval_id(request.form.get("interval_id"))
            if interval_id is None:
                raise ValueError("Interval id is required.")
            store.delete_non_working_interval(interval_id)
        except ValueError:
            flash("删除失败：未找到对应的非工作时间。", "error")
        else:
            flash("非工作时间已删除，工时已自动重算。", "success")
        return _redirect_to_reference(reference_date)

    @app.template_filter("minutes")
    def minutes_filter(value: int | None) -> str:
        return format_minutes(value)

    @app.template_filter("signed_minutes")
    def signed_minutes_filter(value: int) -> str:
        return format_signed_minutes(value)

    @app.template_filter("balance_minutes")
    def balance_minutes_filter(value: int | None) -> str:
        return format_balance_minutes(value)

    @app.template_filter("mode_label")
    def mode_label_filter(value: PeriodMode) -> str:
        return mode_label(value)

    @app.template_filter("reason_label")
    def reason_label_filter(value: str) -> str:
        return reason_label(value)

    @app.template_filter("earliest_reason")
    def earliest_reason_filter(
        required_minutes: int | None,
        target_minutes: int,
    ) -> str:
        return earliest_reason_label(required_minutes, target_minutes)

    @app.template_filter("override_label")
    def override_label_filter(value: DayOverride) -> str:
        return override_label(value)

    from workhours.api import register_api
    register_api(app, store, today_provider, now_provider)
    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)


def _build_dashboard(
    store: WorkHoursStore,
    today: date,
    selected_date: date,
) -> dict[str, object]:
    settings = store.get_settings()
    month_start, month_end = period_bounds(selected_date, PeriodMode.MONTH)
    overrides, holiday_status = _effective_calendar(store, month_start, month_end)
    manual_overrides = store.list_overrides(month_start, month_end)
    leave_days = store.list_leave_days(month_start, month_end)
    entries = store.list_entries(month_start, month_end)
    forecast = build_forecast(selected_date, entries, overrides, settings, leave_days=leave_days)
    month_forecast = build_forecast(selected_date, entries, overrides,
                                    replace(settings, period=PeriodMode.MONTH), leave_days=leave_days)
    selected_entry = entries.get(selected_date)
    selected_preview = _preview_day_forecast(
        selected_date,
        selected_entry.start if selected_entry else None,
        entries,
        overrides,
        settings,
        leave_days,
    )
    enabled_interval_count = sum(
        interval.enabled for interval in settings.non_working_intervals
    )
    return {
        "today": today,
        "selected_date": selected_date,
        "settings": settings,
        "forecast": forecast,
        "entries": entries,
        "overrides": manual_overrides,
        "effective_overrides": overrides,
        "leave_days": leave_days,
        "selected_leave": selected_date in leave_days,
        "holiday_status": holiday_status,
        "month_forecast": month_forecast,
        "month_start": month_start,
        "month_end": month_end,
        "non_working_intervals": settings.non_working_intervals,
        "enabled_interval_count": enabled_interval_count,
        "period_modes": list(PeriodMode),
        "override_kinds": list(DayOverride),
        "selected_entry": selected_entry,
        "selected_preview": selected_preview,
        "today_actual_minutes": _actual_for_today(forecast, selected_date),
        "period_progress": _period_progress(forecast),
    }


def _actual_for_today(forecast: Forecast, today: date) -> int | None:
    day = forecast.days.get(today)
    return day.actual_minutes if day else None


def _period_progress(forecast: Forecast) -> int:
    if forecast.month_target_minutes == 0:
        return 0
    return min(
        100,
        round(
            forecast.month_completed_minutes
            / forecast.month_target_minutes
            * 100
        ),
    )


def format_minutes(value: int | None) -> str:
    if value is None:
        return "-"
    hours, minutes = divmod(value, 60)
    if minutes == 0:
        return f"{hours}小时"
    if hours == 0:
        return f"{minutes}分钟"
    return f"{hours}小时{minutes}分钟"


def format_signed_minutes(value: int) -> str:
    if value == 0:
        return format_minutes(0)
    sign = "+" if value > 0 else "-"
    return f"{sign}{format_minutes(abs(value))}"


def format_balance_minutes(value: int | None) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0分钟"
    return format_signed_minutes(value)


def format_suggested_end(value: time | None, day_offset: int | None) -> str:
    if value is None:
        return "-"
    if day_offset == 1:
        prefix = "次日 "
    elif day_offset and day_offset > 1:
        prefix = f"{day_offset}天后 "
    else:
        prefix = ""
    return f"{prefix}{value.strftime('%H:%M')}"


def earliest_reason_label(
    required_minutes: int | None,
    target_minutes: int,
) -> str:
    if required_minutes is None:
        return ""
    adjustment = target_minutes - required_minutes
    if adjustment > 0:
        return f"余额抵扣{format_minutes(adjustment)}"
    if adjustment < 0:
        return f"今日补足{format_minutes(abs(adjustment))}"
    return f"标准{format_minutes(target_minutes)}"


def mode_label(value: PeriodMode) -> str:
    return "周平均" if value == PeriodMode.WEEK else "月平均"


def reason_label(value: str) -> str:
    labels = {
        "recorded": "已记录",
        "missing_entry": "待补录",
        "minimum_day": "最低8小时",
        "goal_met_minimum": "目标已完成，最低8小时",
        "target_exact": "刚好达标",
        "average_needed": "按剩余目标分摊",
    }
    return labels.get(value, value)


def override_label(value: DayOverride) -> str:
    return "节假日" if value == DayOverride.HOLIDAY else "调休上班"


def _selected_date(default: date) -> date:
    return _parse_date(request.args.get("reference_date")) or default


def _redirect_to_reference(reference_date: date, anchor: str | None = None):
    return redirect(
        url_for(
            "index",
            reference_date=reference_date.isoformat(),
            _anchor=anchor,
        )
    )


def _entry_return_anchor(value: str | None, work_date: date) -> str | None:
    if value == "selected_entry":
        return "selected-entry"
    if value == "prediction":
        return f"prediction-{work_date.isoformat()}"
    return None


def _preview_day_forecast(
    work_date: date,
    start: time | None,
    entries: dict[date, WorkEntry],
    overrides: dict[date, DayOverride],
    settings: ForecastSettings,
    leave_days: set[date] | None = None,
) -> DayForecast | None:
    preview_entries = dict(entries)
    preview_entries[work_date] = WorkEntry(
        work_date=work_date,
        start=start,
        end=None,
        lunch_minutes=90,
    )
    forecast = build_forecast(
        reference_date=work_date,
        entries=preview_entries,
        overrides=overrides,
        settings=settings,
        leave_days=leave_days,
    )
    return forecast.days.get(work_date)


def _record_clock(store: WorkHoursStore, now: datetime, *, start: bool) -> None:
    existing = store.get_entry(now.date()) or WorkEntry(now.date())
    current_time = now.time().replace(second=0, microsecond=0)
    store.save_entry(replace(existing, **({"start": current_time} if start else {"end": current_time})))


def _holiday_result(store: WorkHoursStore, year: int, *, refresh: bool = False) -> HolidayResult:
    if not 2000 <= year <= 2100:
        return HolidayResult(year, {}, "fallback", "该年份超出节假日数据范围，已按星期与手动标记计算")
    return get_holidays(store, year, refresh=refresh,
                        allow_network=current_app.config["HOLIDAY_NETWORK_ENABLED"],
                        fetcher=current_app.config.get("HOLIDAY_FETCHER"))


def _effective_calendar(store: WorkHoursStore, start: date, end: date):
    result = _holiday_result(store, start.year)
    overrides = {
        date.fromisoformat(f"{start.year}-{month_day}"): (
            DayOverride.HOLIDAY if info["isOffDay"] else DayOverride.WORKDAY
        ) for month_day, info in result.holidays.items()
        if start <= date.fromisoformat(f"{start.year}-{month_day}") <= end
    }
    overrides.update(store.list_overrides(start, end))
    return overrides, result


def _preview_payload(preview: DayForecast | None, settings: ForecastSettings):
    if preview is None or preview.required_minutes is None:
        return {"available": False}
    return {
        "available": True,
        "balance_before_minutes": preview.balance_before_minutes,
        "balance_label": format_balance_minutes(preview.balance_before_minutes),
        "day_offset": preview.suggested_end_day_offset,
        "reason_label": earliest_reason_label(preview.required_minutes, settings.target_minutes_per_day),
        "required_label": format_minutes(preview.required_minutes),
        "required_minutes": preview.required_minutes,
        "suggested_end": preview.suggested_end.strftime("%H:%M") if preview.suggested_end else None,
        "suggested_end_label": format_suggested_end(preview.suggested_end, preview.suggested_end_day_offset),
    }


def _parse_required_date(value: str | None) -> date:
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError("Date is required")
    return parsed


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(value)


def _parse_interval_id(value: str | None) -> int | None:
    if not value:
        return None
    interval_id = int(value)
    if interval_id <= 0:
        raise ValueError("Interval id must be positive.")
    return interval_id
