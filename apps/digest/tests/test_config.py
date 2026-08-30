"""Configuration resolution: the rules the CLI is expected to follow."""

import pytest

from digest_cli.config import Config, DigestError, resolve_date, today


def make(**values):
    return Config({"DIGEST_HOME": "/tmp/state", **values})


def test_digest_home_is_required():
    with pytest.raises(DigestError):
        Config({})


def test_derived_paths_hang_off_digest_home():
    cfg = make()
    assert cfg.horizon_dir.name == "horizon"
    assert cfg.summary_path("2026-08-30").name == "horizon-2026-08-30-en.md"
    assert cfg.digest_json("2026-08-30").name == "digest.json"


def test_empty_values_fall_back_to_defaults():
    # config.env.example ships keys set to "", which must not shadow a default.
    assert make(PODCAST_TTS_MODEL="").podcast_options()["tts_model"] == "edge"
    assert make(PODCAST_TTS_MODEL="openai").podcast_options()["tts_model"] == "openai"


def test_flag_parsing():
    assert make(PODCAST_ENABLED="true").flag("PODCAST_ENABLED")
    assert make(PODCAST_ENABLED="YES").flag("PODCAST_ENABLED")
    assert not make(PODCAST_ENABLED="false").flag("PODCAST_ENABLED")
    assert make().flag("PODCAST_ENABLED", default=True)


def test_schedule_time_defaults():
    assert make().schedule_time == (6, 45)
    assert make(HORIZON_HOUR="7", HORIZON_MINUTE="5").schedule_time == (7, 5)


def test_slack_token_precedence(tmp_path, monkeypatch):
    token_file = tmp_path / "slack.env"
    token_file.write_text("SLACK_BOT_TOKEN=from-file\n")
    cfg = make(SLACK_TOKEN_FILE=str(token_file), SLACK_BOT_TOKEN="from-config")

    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    assert cfg.slack_token("from-flag") == "from-flag"
    assert cfg.slack_token() == "from-config"

    monkeypatch.setenv("SLACK_BOT_TOKEN", "from-env")
    assert cfg.slack_token() == "from-env"


def test_slack_token_file_is_the_last_resort(tmp_path, monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    token_file = tmp_path / "slack.env"
    token_file.write_text("SLACK_BOT_TOKEN=from-file\n")
    cfg = make(SLACK_TOKEN_FILE=str(token_file))
    assert cfg.slack_token() == "from-file"
    assert cfg.has_slack_token()


def test_a_configured_but_missing_token_file_is_not_a_token(tmp_path, monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    cfg = make(SLACK_TOKEN_FILE=str(tmp_path / "absent.env"))
    assert cfg.slack_token() == ""
    assert not cfg.has_slack_token()


def test_resolve_date():
    assert resolve_date(None) == today()
    assert resolve_date("2026-08-30") == "2026-08-30"
    with pytest.raises(DigestError):
        resolve_date("30-08-2026")
