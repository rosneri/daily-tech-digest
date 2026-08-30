"""Episode discovery across the two locations episodes can land in."""

from digest_podcast import SUPPORTED_PYTHON, locate, venv_python


def test_prefers_the_podcasts_directory(tmp_path):
    podcasts, digests = tmp_path / "podcasts", tmp_path / "digests"
    (podcasts).mkdir()
    (digests / "2026-08-30").mkdir(parents=True)
    (podcasts / "digest-2026-08-30.mp3").write_bytes(b"x" * 2_000_000)
    (digests / "2026-08-30" / "podcast.mp3").write_bytes(b"y" * 10)

    mp3, size_mb, transcript = locate(podcasts, digests, "2026-08-30")
    assert mp3.parent == podcasts
    assert size_mb == 2.0
    assert transcript is None


def test_falls_back_to_the_digest_folder(tmp_path):
    podcasts, digests = tmp_path / "podcasts", tmp_path / "digests"
    podcasts.mkdir()
    (digests / "2026-08-30").mkdir(parents=True)
    (digests / "2026-08-30" / "podcast.mp3").write_bytes(b"y" * 1_000)
    mp3, _, _ = locate(podcasts, digests, "2026-08-30")
    assert mp3.name == "podcast.mp3"


def test_zero_byte_files_do_not_count_as_an_episode(tmp_path):
    podcasts, digests = tmp_path / "podcasts", tmp_path / "digests"
    podcasts.mkdir(); digests.mkdir()
    (podcasts / "digest-2026-08-30.mp3").touch()
    assert locate(podcasts, digests, "2026-08-30") == (None, 0.0, None)


def test_transcript_is_found_when_present(tmp_path):
    podcasts, digests = tmp_path / "podcasts", tmp_path / "digests"
    (podcasts / "transcripts").mkdir(parents=True); digests.mkdir()
    (podcasts / "digest-2026-08-30.mp3").write_bytes(b"x" * 100)
    (podcasts / "transcripts" / "transcript-2026-08-30.txt").write_text("hi")
    assert locate(podcasts, digests, "2026-08-30")[2].name == "transcript-2026-08-30.txt"


def test_venv_python_location(tmp_path):
    assert venv_python(tmp_path).parts[-2:] == ("bin", "python")


def test_python_314_is_not_claimed_as_supported():
    # podcastfy's tree still fails to build there; see .prototools.
    assert "3.14" not in SUPPORTED_PYTHON
