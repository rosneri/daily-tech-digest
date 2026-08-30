"""Plist construction. Nothing here touches launchctl."""

import plistlib

from digest_launchd import LaunchAgent, default_path_env


def agent(tmp_path):
    return LaunchAgent("com.example.job", agent_dir=tmp_path)


def test_definition_shape(tmp_path):
    plist = agent(tmp_path).definition(["/usr/bin/python3", "/tmp/x", "run"], 6, 45)
    assert plist["Label"] == "com.example.job"
    assert plist["ProgramArguments"] == ["/usr/bin/python3", "/tmp/x", "run"]
    assert plist["StartCalendarInterval"] == {"Hour": 6, "Minute": 45}


def test_path_env_includes_homebrew_and_uv():
    # launchd's default PATH has neither; a job that omits this fails at 06:45.
    path = default_path_env()
    assert "/opt/homebrew/bin" in path
    assert ".local/bin" in path


def test_env_overrides_merge_over_defaults(tmp_path):
    plist = agent(tmp_path).definition(["x"], 1, 2, env={"COLUMNS": "200"})
    assert plist["EnvironmentVariables"]["COLUMNS"] == "200"
    assert "PATH" in plist["EnvironmentVariables"]


def test_write_then_read_roundtrip(tmp_path):
    job = agent(tmp_path)
    job.write(job.definition(["x"], 7, 5, stdout=tmp_path / "o.log"))
    assert job.read()["StandardOutPath"] == str(tmp_path / "o.log")


def test_program_args_are_stringified(tmp_path):
    from pathlib import Path
    job = agent(tmp_path)
    job.write(job.definition([Path("/bin/python3"), Path("/tmp/digest")], 6, 45))
    with open(job.path, "rb") as handle:
        assert plistlib.load(handle)["ProgramArguments"] == ["/bin/python3", "/tmp/digest"]


def test_retarget_rewrites_and_backs_up(tmp_path):
    job = agent(tmp_path)
    job.write(job.definition(["/old/path/digest", "run"], 6, 45))
    backup = job.retarget("/old/path", "/new/path")
    assert backup.exists()
    assert job.read()["ProgramArguments"][0] == "/new/path/digest"


def test_retarget_is_a_noop_when_absent(tmp_path):
    job = agent(tmp_path)
    job.write(job.definition(["/x"], 6, 45))
    assert job.retarget("/nothing", "/else") is None
