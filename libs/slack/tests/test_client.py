"""Client behaviour that does not need a live workspace."""

import pytest

from digest_slack import SlackClient, SlackError, fallback_text, normalise_reactions


def test_requires_a_token():
    with pytest.raises(SlackError):
        SlackClient("")


def test_channel_is_required_per_call_or_at_construction():
    client = SlackClient("xoxb-test")
    with pytest.raises(SlackError):
        client._channel()
    assert client._channel("C123") == "C123"
    assert SlackClient("xoxb-test", "C999")._channel() == "C999"


def dm_client(monkeypatch, user="U1"):
    """A client whose Web API is a counter, so DM resolution can be observed."""
    client = SlackClient("xoxb-test", user=user)
    calls = []

    def fake_call(method, payload=None, params=None):
        calls.append((method, payload, params))
        return {"channel": {"id": "D1"}, "ts": "1.1"}

    monkeypatch.setattr(client, "call", fake_call)
    return client, calls


def test_a_user_resolves_to_a_dm_channel(monkeypatch):
    client, calls = dm_client(monkeypatch)
    assert client._channel() == "D1"
    assert calls == [("conversations.open", {"users": "U1"}, None)]


def test_the_dm_lookup_happens_once(monkeypatch):
    client, calls = dm_client(monkeypatch)
    client._channel()
    client._channel()
    assert len(calls) == 1


def test_an_explicit_channel_beats_the_dm(monkeypatch):
    client, calls = dm_client(monkeypatch)
    assert client._channel("C123") == "C123"
    assert calls == []


def test_open_dm_needs_a_user():
    with pytest.raises(SlackError, match="no user specified"):
        SlackClient("xoxb-test").open_dm()


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


def test_post_rejects_an_empty_message():
    with pytest.raises(SlackError, match="no text and no blocks"):
        SlackClient("xoxb-test", "C1").post()


def test_post_rejects_malformed_blocks():
    client = SlackClient("xoxb-test", "C1")
    with pytest.raises(SlackError, match="must be a JSON array"):
        client.post(blocks={"type": "section"})
    with pytest.raises(SlackError, match="blocks is empty"):
        client.post(blocks=[])
    with pytest.raises(SlackError, match="too many blocks"):
        client.post(blocks=[{"type": "divider"}] * 51)


def test_post_sends_blocks_with_derived_fallback_text(monkeypatch):
    client = SlackClient("xoxb-test", "C1")
    sent = {}

    def fake_call(method, payload=None, params=None):
        sent.update(payload)
        return {"ts": "1.1", "channel": "C1"}

    monkeypatch.setattr(client, "call", fake_call)
    client.post(blocks=[{"type": "section",
                         "text": {"type": "mrkdwn", "text": "*1. A headline*\nBody"}}])
    assert sent["text"] == "*1. A headline*"
    assert sent["blocks"][0]["type"] == "section"


def test_explicit_text_wins_over_the_derived_fallback(monkeypatch):
    client = SlackClient("xoxb-test", "C1")
    sent = {}
    monkeypatch.setattr(client, "call",
                        lambda m, payload=None, params=None: (sent.update(payload),
                                                              {"ts": "1.1", "channel": "C1"})[1])
    client.post("notify me", blocks=[{"type": "divider"}])
    assert sent["text"] == "notify me"


def test_fallback_text_reads_the_first_human_string():
    assert fallback_text([{"type": "divider"},
                          {"type": "header",
                           "text": {"type": "plain_text", "text": "Digest"}}]) == "Digest"
    assert fallback_text([{"type": "section",
                           "fields": [{"type": "mrkdwn", "text": "field one"}]}]) == "field one"


def test_fallback_text_never_returns_empty():
    # A blocks-only message with no text at all would otherwise arrive as a
    # silent, unlabelled DM.
    assert fallback_text([{"type": "divider"}, {"type": "image"}])
    assert fallback_text([])
