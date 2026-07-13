from pathlib import Path

import httpx
import pytest

from backend.db import connect, initialize_database
from backend.repositories.holidays import set_holiday_cache
from backend.services.holidays import get_holidays


@pytest.mark.anyio
async def test_owned_client_disables_environment_proxy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "ALL_PROXY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "http_proxy",
        "https_proxy",
    ):
        monkeypatch.setenv(name, "socks5h://127.0.0.1:7897")

    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    real_async_client = httpx.AsyncClient
    constructor_kwargs: dict[str, object] = {}
    owned_clients: list[httpx.AsyncClient] = []

    def create_client(**kwargs: object) -> httpx.AsyncClient:
        constructor_kwargs.update(kwargs)
        owned_client = real_async_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(503)
            ),
            timeout=kwargs["timeout"],
            trust_env=False,
        )
        owned_clients.append(owned_client)
        return owned_client

    monkeypatch.setattr(
        "backend.services.holidays.httpx.AsyncClient",
        create_client,
    )
    result = await get_holidays(conn, 2026)
    conn.close()

    assert constructor_kwargs == {"timeout": 5.0, "trust_env": False}
    assert owned_clients[0].is_closed
    assert result.source == "fallback"


@pytest.mark.anyio
async def test_cache_hit_does_not_call_remote(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    payload = {"01-01": {"name": "元旦", "isOffDay": True}}
    with conn:
        set_holiday_cache(conn, 2026, payload, "2026-01-01T00:00:00Z")

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("remote request should not happen")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(unexpected_request)
    ) as client:
        result = await get_holidays(conn, 2026, client)
    conn.close()

    assert result.source == "cache"
    assert result.holidays == payload


@pytest.mark.anyio
async def test_remote_success_is_cached(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)

    def remote(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "days": [
                    {
                        "name": "元旦",
                        "date": "2026-01-01",
                        "isOffDay": True,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(remote)
    ) as client:
        first = await get_holidays(conn, 2026, client)
        second = await get_holidays(conn, 2026, client)
    conn.close()

    assert first.source == "remote"
    assert second.source == "cache"
    assert first.holidays["01-01"]["name"] == "元旦"


@pytest.mark.anyio
async def test_both_remote_sources_fail_without_caching(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    calls: list[str] = []

    def failed(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(503)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(failed)
    ) as client:
        result = await get_holidays(conn, 2026, client)
    count = conn.execute(
        "SELECT COUNT(*) FROM holiday_cache WHERE year = 2026"
    ).fetchone()[0]
    conn.close()

    assert calls == [
        "https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/2026.json",
        "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/2026.json",
    ]
    assert result.source == "fallback"
    assert result.holidays == {}
    assert count == 0


@pytest.mark.anyio
async def test_empty_remote_results_are_not_cached(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)

    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"days": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(empty)
    ) as client:
        result = await get_holidays(conn, 2026, client)
    count = conn.execute(
        "SELECT COUNT(*) FROM holiday_cache WHERE year = 2026"
    ).fetchone()[0]
    conn.close()

    assert result.source == "fallback"
    assert result.holidays == {}
    assert count == 0
