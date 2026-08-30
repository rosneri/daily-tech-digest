"""Parsing rules that config.env actually depends on."""

import os

from digest_shellenv import parse, parse_file, read_value


def test_quoting_and_comments():
    values = parse('\n'.join([
        '# a comment',
        'PLAIN=value',
        'DOUBLE="spaced value"',
        "SINGLE='literal ${NOPE}'",
        'EXPORTED=export-is-stripped',
        'export ALSO=yes',
        'TRAILING=value # not part of it',
    ]))
    assert values["PLAIN"] == "value"
    assert values["DOUBLE"] == "spaced value"
    assert values["SINGLE"] == "literal ${NOPE}", "single quotes must not expand"
    assert values["EXPORTED"] == "export-is-stripped"
    assert values["ALSO"] == "yes"
    assert values["TRAILING"] == "value"


def test_expansion_uses_base_then_earlier_keys():
    values = parse("ROOT=/base\nCHILD=${ROOT}/child\nFROM_ENV=$OUTER/x",
                   base={"OUTER": "/outer"})
    assert values["CHILD"] == "/base/child"
    assert values["FROM_ENV"] == "/outer/x"


def test_unknown_reference_becomes_empty_like_a_shell():
    assert parse("X=${NOT_SET}/tail", base={})["X"] == "/tail"


def test_blank_and_malformed_lines_are_skipped():
    assert parse("\n\nnot a pair\n=novalue\nOK=1") == {"OK": "1"}


def test_parse_file_missing_ok(tmp_path):
    assert parse_file(tmp_path / "nope.env", missing_ok=True) == {}


def test_read_value(tmp_path):
    path = tmp_path / "secret.env"
    path.write_text("SLACK_BOT_TOKEN=xoxb-123\n")
    assert read_value(path, "SLACK_BOT_TOKEN") == "xoxb-123"
    assert read_value(path, "ABSENT", "fallback") == "fallback"
