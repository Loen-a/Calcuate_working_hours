from datetime import time

import pytest

from workhours.domain import NonWorkingInterval
from workhours.storage import WorkHoursStore


def test_store_seeds_default_intervals_once(tmp_path):
    database_path = tmp_path / "workhours.sqlite3"
    store = WorkHoursStore(database_path)

    intervals = store.list_non_working_intervals()

    assert [
        (item.name, item.start, item.end, item.enabled)
        for item in intervals
    ] == [
        ("午休", time(12), time(13, 30), True),
        ("晚间休息", time(19, 30), time(20), True),
    ]
    assert all(item.interval_id is not None for item in intervals)
    assert store.get_settings().non_working_intervals == tuple(intervals)

    for item in intervals:
        store.delete_non_working_interval(item.interval_id)

    reopened_store = WorkHoursStore(database_path)
    assert reopened_store.list_non_working_intervals() == []


def test_store_creates_updates_and_deletes_interval(tmp_path):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")

    created = store.save_non_working_interval(
        NonWorkingInterval(None, "下午休息", time(15), time(15, 15))
    )
    assert created.interval_id is not None

    updated = store.save_non_working_interval(
        NonWorkingInterval(
            created.interval_id,
            "下午茶",
            time(15, 10),
            time(15, 30),
            enabled=False,
        )
    )
    assert updated == NonWorkingInterval(
        created.interval_id,
        "下午茶",
        time(15, 10),
        time(15, 30),
        enabled=False,
    )
    assert updated in store.list_non_working_intervals()

    store.delete_non_working_interval(created.interval_id)
    assert updated not in store.list_non_working_intervals()


@pytest.mark.parametrize(
    "interval",
    [
        NonWorkingInterval(None, "", time(12), time(13)),
        NonWorkingInterval(None, "无效", time(13), time(13)),
        NonWorkingInterval(None, "无效", time(14), time(13)),
    ],
)
def test_store_rejects_invalid_interval(tmp_path, interval):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")

    with pytest.raises(ValueError):
        store.save_non_working_interval(interval)
