import json

import httpx
import pytest

from app.email.gmail_api import GmailApiClient


def response(status: int, payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(payload).encode("utf-8"))


@pytest.mark.asyncio
async def test_initial_sync_is_bounded_and_requests_metadata_only() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return response(200, {"access_token": "access-token"})
        if request.url.path.endswith("/profile"):
            return response(200, {"historyId": "200"})
        if request.url.path.endswith("/messages"):
            assert request.url.params["q"] == "newer_than:2d"
            assert request.url.params["maxResults"] == "2"
            return response(200, {"messages": [{"id": "one"}, {"id": "two"}]})
        assert request.url.path.endswith("/messages/one") or request.url.path.endswith(
            "/messages/two"
        )
        assert request.url.params["format"] == "metadata"
        return response(
            200,
            {
                "id": request.url.path.rsplit("/", 1)[-1],
                "internalDate": "1780000000000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "security@example.test"},
                        {"name": "Subject", "value": "Security alert"},
                    ]
                },
            },
        )

    client = GmailApiClient(
        "client",
        "secret",
        initial_lookback_hours=48,
        initial_max_messages=2,
        transport=httpx.MockTransport(handler),
    )
    batch = await client.sync("refresh-token", None)
    assert [item.message_id for item in batch.messages] == ["one", "two"]
    assert all(not item.body for item in batch.messages)
    assert batch.history_id == "200"
    assert "refresh-token" not in " ".join(str(call.url) for call in calls)


@pytest.mark.asyncio
async def test_incremental_history_sync_avoids_initial_mailbox_query() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.host == "oauth2.googleapis.com":
            return response(200, {"access_token": "access-token"})
        if request.url.path.endswith("/profile"):
            return response(200, {"historyId": "202"})
        if request.url.path.endswith("/history"):
            assert request.url.params["startHistoryId"] == "200"
            return response(
                200,
                {
                    "historyId": "201",
                    "history": [
                        {"messagesAdded": [{"message": {"id": "new"}}]},
                        {"messagesAdded": [{"message": {"id": "new"}}]},
                        {"messagesAdded": [{"message": {"id": "archived"}}]},
                    ],
                },
            )
        message_id = request.url.path.rsplit("/", 1)[-1]
        return response(
            200,
            {
                "id": message_id,
                "labelIds": ["INBOX"] if message_id == "new" else ["ARCHIVE"],
                "payload": {"headers": [{"name": "Subject", "value": "Hi"}]},
            },
        )

    client = GmailApiClient("client", "secret", transport=httpx.MockTransport(handler))
    batch = await client.sync("refresh-token", "200")
    assert [item.message_id for item in batch.messages] == ["new"]
    assert batch.history_id == "201"
    assert not any(path.endswith("/messages") for path in paths)


@pytest.mark.asyncio
async def test_expired_history_uses_bounded_recovery_sync() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.host == "oauth2.googleapis.com":
            return response(200, {"access_token": "access-token"})
        if request.url.path.endswith("/profile"):
            return response(200, {"historyId": "300"})
        if request.url.path.endswith("/history"):
            return response(404, {"error": "historyId invalid"})
        if request.url.path.endswith("/messages"):
            return response(200, {"messages": []})
        raise AssertionError(request.url.path)

    client = GmailApiClient("client", "secret", transport=httpx.MockTransport(handler))
    batch = await client.sync("refresh-token", "old")
    assert batch.messages == []
    assert batch.history_id == "300"
    assert any(path.endswith("/history") for path in calls)
    assert any(path.endswith("/messages") for path in calls)
