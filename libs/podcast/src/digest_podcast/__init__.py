"""Adapter for podcastfy: build its venv, drive the generator, locate episodes.

podcastfy needs Python >=3.11,<4 and pulls a large dependency tree, so it lives
in its own venv rather than in the workspace one. That is also why the generator
itself (``scripts/generate_podcast.py``, in this project) is a standalone script
run as a subprocess: it executes under a different interpreter than this module.
"""

import shutil
import subprocess
import sys
from pathlib import Path

__all__ = ["PodcastError", "install_venv", "generate", "locate", "venv_python",
           "SUPPORTED_PYTHON"]

SUPPORTED_PYTHON = ("3.11", "3.12", "3.13")


class PodcastError(Exception):
    """The venv could not be built, or generation failed."""


def venv_python(venv_dir):
    return Path(venv_dir) / "bin" / "python"


def install_venv(venv_dir, python_version="3.13", on_event=None):
    """Create the podcastfy venv, preferring uv for an isolated interpreter."""
    venv_dir = Path(venv_dir)
    say = on_event or (lambda level, message: None)

    if shutil.which("uv"):
        say("log", f"Creating podcast venv with uv (Python {python_version})")
        _run(["uv", "venv", "--quiet", "--python", python_version, str(venv_dir)])
        say("log", "Installing podcastfy")
        # podcastfy 0.4.x imports playwright at module load without declaring it
        # as a dependency, so client.py fails to import unless we add it.
        _run(["uv", "pip", "install", "--quiet", "podcastfy", "playwright"],
             env_extra={"VIRTUAL_ENV": str(venv_dir)})
    else:
        version = subprocess.run(
            [sys.executable, "-c", 'import sys;print("%d.%d"%sys.version_info[:2])'],
            capture_output=True, text=True,
        ).stdout.strip()
        if version not in SUPPORTED_PYTHON:
            raise PodcastError(
                f"podcastfy needs Python {'/'.join(SUPPORTED_PYTHON)}, found {version}. "
                "Install uv for an isolated interpreter.")
        say("log", f"Creating podcast venv with python3 {version}")
        _run([sys.executable, "-m", "venv", str(venv_dir)])
        pip = venv_dir / "bin" / "pip"
        _run([str(pip), "install", "--quiet", "--upgrade", "pip"])
        say("log", "Installing podcastfy")
        _run([str(pip), "install", "--quiet", "podcastfy", "playwright"])  # see note above

    # ffmpeg is what actually stitches the audio segments together.
    if not shutil.which("ffmpeg"):
        say("warn", "ffmpeg not found — podcastfy needs it to assemble audio")
        say("warn", "install with: brew install ffmpeg")

    return installed_version(venv_dir)


def installed_version(venv_dir):
    result = subprocess.run(
        [str(venv_python(venv_dir)), "-c", "import podcastfy;print(podcastfy.__version__)"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() or "installed"


def generate(venv_dir, generator, summary, day, out_dir, options, extra=None, env=None):
    """Run the generator script inside the podcastfy venv.

    `options` is the resolved settings mapping (voices, model, story count);
    the caller owns defaults, this just marshals them onto the command line.
    """
    python = venv_python(venv_dir)
    if not python.exists():
        raise PodcastError(f"podcast venv missing at {venv_dir}. Run: digest install-podcast")
    summary = Path(summary)
    if not summary.exists():
        raise PodcastError(f"no Horizon summary for {day} at {summary}")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    command = [
        str(python), str(generator),
        "--summary", str(summary),
        "--date", day,
        "--out-dir", str(out_dir),
        "--max-stories", str(options["max_stories"]),
        "--tts-model", options["tts_model"],
        "--script-engine", options["script_engine"],
        "--llm-model", options["llm_model"],
        "--llm-api-key-label", options["llm_api_key_label"],
        "--name", options["name"],
        "--tagline", options["tagline"],
        "--voice-1", options["voice_1"],
        "--voice-2", options["voice_2"],
        *(extra or []),
    ]
    status = subprocess.run(command, env=env).returncode
    if status != 0:
        raise PodcastError(f"generation failed (exit {status})")


def locate(podcast_dir, digests_dir, day):
    """Find the episode for `day`. Returns (mp3 or None, size_mb, transcript or None).

    Two locations are checked because the standalone generator writes into the
    per-day digest folder while the packaged one writes into podcasts/.
    """
    candidates = [
        Path(podcast_dir) / f"digest-{day}.mp3",
        Path(digests_dir) / day / "podcast.mp3",
    ]
    mp3 = next((p for p in candidates if p.is_file() and p.stat().st_size > 0), None)
    transcript = Path(podcast_dir) / "transcripts" / f"transcript-{day}.txt"
    return (
        mp3,
        round(mp3.stat().st_size / 1_000_000, 1) if mp3 else 0.0,
        transcript if transcript.is_file() else None,
    )


def _run(command, env_extra=None):
    import os
    env = {**os.environ, **(env_extra or {})} if env_extra else None
    result = subprocess.run([str(c) for c in command], env=env)
    if result.returncode != 0:
        raise PodcastError(f"{command[0]} failed (exit {result.returncode})")
