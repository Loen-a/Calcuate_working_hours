"""Shared JSON boundary; all attendance and forecasts come from the Python domain."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone

from flask import Response, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from workhours.backup import build_backup, restore_backup
from workhours.domain import DayOverride, NonWorkingInterval, PeriodMode, WorkEntry
from workhours.web import (
    _build_dashboard, _holiday_result, _preview_payload, _record_clock,
)


def _date(raw: object) -> date:
    if not isinstance(raw, str):
        raise ValueError("日期须使用 YYYY-MM-DD 格式")
    try:
        result = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("日期无效，请使用 YYYY-MM-DD 格式") from exc
    if result.isoformat() != raw:
        raise ValueError("日期须使用 YYYY-MM-DD 格式")
    return result


def _time(raw: object) -> time | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{2}:[0-9]{2}", raw):
        raise ValueError("时间须使用 HH:MM 格式")
    try:
        return time.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("时间无效，请使用 HH:MM 格式") from exc


def _body(allowed: set[str], required: set[str] | None = None) -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("请求须包含 JSON 对象")
    if set(data) - allowed or (required or set()) - set(data):
        raise ValueError("请求字段缺失或包含不支持的字段")
    return data


def _boolean(raw: object) -> bool:
    if type(raw) is not bool:
        raise ValueError("状态须为 true 或 false")
    return raw


def _stamp(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


def dashboard_payload(store, today: date, selected_date: date) -> dict:
    context = _build_dashboard(store, today, selected_date)
    monthly = context["month_forecast"]
    forecast = context["forecast"]
    settings = context["settings"]
    holiday_status = context["holiday_status"]
    manual = context["overrides"]
    leaves = context["leave_days"]
    days = []
    current = context["month_start"]
    while current <= context["month_end"]:
        item = monthly.days.get(current)
        entry = context["entries"].get(current)
        override = manual.get(current)
        auto = holiday_status.holidays.get(current.strftime("%m-%d"))
        name = "工作日" if current.weekday() < 5 else "周末"
        if auto:
            name = auto["name"] + ("" if auto["isOffDay"] else " · 上班")
        if override:
            name = "手动休息" if override == DayOverride.HOLIDAY else "调休上班"
        if current in leaves:
            name = "全天请假"
        days.append({
            "date": current.isoformat(), "is_workday": item is not None,
            "leave": current in leaves, "calendar_name": name,
            "manual_override": override.value if override else None,
            "entry": {"start_time": _stamp(entry.start), "end_time": _stamp(entry.end)} if entry else None,
            "actual_minutes": item.actual_minutes if item else None,
            "daily_balance_minutes": item.daily_balance_minutes if item else None,
            "cumulative_balance_minutes": item.cumulative_balance_minutes if item else None,
            "balance_before_minutes": item.balance_before_minutes if item else 0,
            "required_minutes": item.required_minutes if item else None,
            "recommended_minutes": item.recommended_minutes if item else None,
            "suggested_end": _stamp(item.suggested_end) if item else None,
            "suggested_end_day_offset": item.suggested_end_day_offset if item else None,
            "reason": item.reason if item else ("leave" if current in leaves else "rest"),
            "compliant": item.compliant if item else None,
        })
        if current == context["month_end"]:
            break
        current += timedelta(days=1)
    return {
        "today": today.isoformat(), "selected_date": selected_date.isoformat(),
        "theme": store.get_theme(),
        "settings": {"period": settings.period.value,
                     "target_minutes_per_day": settings.target_minutes_per_day,
                     "minimum_minutes_per_day": settings.minimum_minutes_per_day},
        "intervals": [{"interval_id": interval.interval_id, "name": interval.name,
                       "start_time": _stamp(interval.start), "end_time": _stamp(interval.end),
                       "enabled": interval.enabled} for interval in settings.non_working_intervals],
        "days": days,
        "selected_preview": _preview_payload(context["selected_preview"], settings),
        "month": {
            "start": context["month_start"].isoformat(), "end": context["month_end"].isoformat(),
            "target_minutes": monthly.month_target_minutes,
            "completed_minutes": monthly.month_completed_minutes,
            "balance_minutes": sum(item.daily_balance_minutes or 0 for item in monthly.days.values()),
            "remaining_target_minutes": monthly.remaining_target_minutes,
            "workday_count": len(monthly.workdays),
            "recorded_days": sum(item.actual_minutes is not None for item in monthly.days.values()),
            "missing_history_days": [day.isoformat() for day in monthly.missing_history_days],
        },
        "forecast": {
            "period_start": forecast.period_start.isoformat(), "period_end": forecast.period_end.isoformat(),
            "target_minutes": forecast.target_minutes, "completed_minutes": forecast.completed_minutes,
            "remaining_target_minutes": forecast.remaining_target_minutes,
            "carryover_minutes": forecast.carryover_minutes, "goal_met": forecast.goal_met,
        },
        "holiday_status": {"year": holiday_status.year, "source": holiday_status.source,
                           "warning": holiday_status.warning},
    }


def register_api(app, store, today_provider, now_provider) -> None:
    @app.errorhandler(ValueError)
    def invalid_value(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(BadRequest)
    def invalid_request(error):
        return jsonify(error="请求内容不完整或格式无效"), 400

    @app.errorhandler(RequestEntityTooLarge)
    def oversized_request(error):
        return jsonify(error="备份文件不能超过 16 MiB"), 413

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception("Database operation failed")
        return jsonify(error="数据库操作失败，请重试；备份导入失败时原数据会保留"), 500

    @app.get("/api/dashboard")
    def get_dashboard():
        today = today_provider()
        selected = _date(request.args["reference_date"]) if "reference_date" in request.args else today
        return jsonify(dashboard_payload(store, today, selected))

    @app.get("/api/weather")
    def get_calendar_weather():
        from workhours.weather import get_weather

        raw_month = request.args.get("month", "")
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", raw_month):
            raise ValueError("月份须使用 YYYY-MM 格式")
        month = _date(raw_month + "-01")
        clock = app.config.get("WEATHER_NOW_PROVIDER")
        weather = get_weather(
            store, month, now=clock() if clock else None,
            allow_network=app.config.get("WEATHER_NETWORK_ENABLED", True),
            fetcher=app.config.get("WEATHER_FETCHER"),
        )
        response = jsonify(asdict(weather))
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/air-quality")
    def get_calendar_air_quality():
        from workhours.air_quality import get_air_quality

        raw_month = request.args.get("month", "")
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", raw_month):
            raise ValueError("月份须使用 YYYY-MM 格式")
        month = _date(raw_month + "-01")
        clock = app.config.get("WEATHER_NOW_PROVIDER")
        result = get_air_quality(
            store, month, now=clock() if clock else None,
            allow_network=app.config.get("WEATHER_NETWORK_ENABLED", True) and app.config.get("AIR_QUALITY_NETWORK_ENABLED", True),
            fetcher=app.config.get("AIR_QUALITY_FETCHER"),
        )
        response = jsonify(asdict(result))
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.put("/api/entries/<work_date>")
    def put_entry(work_date):
        work_date = _date(work_date)
        body = _body({"start_time", "end_time"}, {"start_time", "end_time"})
        start, end = _time(body["start_time"]), _time(body["end_time"])
        existing = store.get_entry(work_date)
        store.save_entry(WorkEntry(work_date, start, end, existing.lunch_minutes if existing else 90))
        return jsonify(start_time=_stamp(start), end_time=_stamp(end))

    @app.delete("/api/entries/<work_date>")
    def delete_entry(work_date):
        store.delete_entry(_date(work_date))
        return jsonify(ok=True)

    @app.post("/api/clock-in")
    def api_clock_in():
        now = now_provider()
        _record_clock(store, now, start=True)
        return jsonify(date=now.date().isoformat())

    @app.post("/api/clock-out")
    def api_clock_out():
        now = now_provider()
        _record_clock(store, now, start=False)
        return jsonify(date=now.date().isoformat())

    @app.put("/api/leaves/<work_date>")
    def put_leave(work_date):
        work_date = _date(work_date)
        body = _body({"enabled"}, {"enabled"})
        store.set_leave(work_date, _boolean(body["enabled"]))
        return jsonify(ok=True)

    @app.put("/api/calendar/<work_date>")
    def put_calendar(work_date):
        work_date = _date(work_date)
        body = _body({"kind"}, {"kind"})
        if body["kind"] not in ("holiday", "workday"):
            raise ValueError("日历类型只能为 holiday 或 workday")
        store.set_override(work_date, DayOverride(body["kind"]))
        return jsonify(ok=True)

    @app.delete("/api/calendar/<work_date>")
    def delete_calendar(work_date):
        store.delete_override(_date(work_date))
        return jsonify(ok=True)

    @app.put("/api/settings")
    def put_settings():
        body = _body({"period", "theme"})
        if not body:
            raise ValueError("请选择需要修改的设置")
        if "period" in body and body["period"] not in ("week", "month"):
            raise ValueError("统计周期只能为 week 或 month")
        if "theme" in body and body["theme"] not in ("cool", "teal", "classic"):
            raise ValueError("主题只能为 cool、teal 或 classic")
        if "period" in body:
            store.set_period(PeriodMode(body["period"]))
        if "theme" in body:
            store.set_theme(body["theme"])
        return jsonify(ok=True)

    @app.post("/api/non-working-intervals")
    def put_interval():
        body = _body({"interval_id", "name", "start_time", "end_time", "enabled"},
                     {"name", "start_time", "end_time", "enabled"})
        interval_id = body.get("interval_id")
        if interval_id is not None and (type(interval_id) is not int or interval_id <= 0):
            raise ValueError("非工作时段编号无效")
        if not isinstance(body["name"], str):
            raise ValueError("时段名称须为文字")
        start, end = _time(body["start_time"]), _time(body["end_time"])
        if start is None or end is None:
            raise ValueError("非工作时段须填写开始与结束时间")
        interval = store.save_non_working_interval(NonWorkingInterval(
            interval_id, body["name"], start, end, _boolean(body["enabled"])))
        return jsonify(interval_id=interval.interval_id)

    @app.delete("/api/non-working-intervals/<int:interval_id>")
    def delete_interval(interval_id):
        store.delete_non_working_interval(interval_id)
        return jsonify(ok=True)

    @app.post("/api/holidays/<int:year>/refresh")
    def api_refresh_holidays(year):
        result = _holiday_result(store, year, refresh=True)
        return jsonify(year=result.year, source=result.source, warning=result.warning)

    @app.get("/api/backup")
    def export_backup():
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S-%f")
        return Response(json.dumps(build_backup(store), ensure_ascii=False, indent=2),
                        mimetype="application/json", headers={
                            "Content-Disposition": f'attachment; filename="workhours-{stamp}.json"'})

    @app.post("/api/backup")
    def import_backup():
        upload = request.files.get("file")
        if upload is None:
            raise ValueError("请选择 JSON 备份文件")
        try:
            raw = json.loads(upload.read().decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("备份文件不是有效的 UTF-8 JSON") from exc
        return jsonify(restore_backup(store, raw))
