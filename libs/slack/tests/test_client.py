"""Client behaviour that does not need a live workspace."""

import pytest

from digest_slack import SlackClient, SlackError, normalise_reactions


def test_requires_a_token():
    with pytest.raises(SlackError):
        SlackClient("")


def test_channel_is_required_per_call_or_at_construction():
    client = SlackClient("xoxb-test")
    with pytest.raises(SlackError):
        client._channel()
    assert client._channel("C123") == "C123"
    assert SlackClient("xoxb-test", "C999")._channel() == "C999"


def test_error_carries_the_machine_readable_code():
    exc = SlackError("chat.postMessage", "not_in_channel")
    assert exc.error == "not_in_channel"
    assert "chat.postMessage" in str(exc)


def test_missing_scope_is_surfaced():
    assert "missing scope: files:write" in str(
        SlackError("files.completeUploadExternal", "missing_scope", "files:write"))


def test_upload_rejects_a_missing_file(tmp_path):
    with pytest.raises(SlackError, match="file not found"):
        SlackClient("xoxb-test", "C1").upload_file(tmp_path / "absent.mp3")


def test_upload_rejects_an_empty_file(tmp_path):
    empty = tmp_path / "empty.mp3"
    empty.touch()
    with pytest.raises(SlackError, match="file is empty"):
        SlackClient("xoxb-test", "C1").upload_file(empty)


def test_normalise_reactions_defaults():
    assert normalise_reactions({}) == []
    assert normalise_reactions({"reactions": [{"name": "fire", "count": 2}]}) == [
        {"name": "fire", "count": 2, "users": []}
    ]
