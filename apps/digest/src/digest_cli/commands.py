"""Wiring between Config and the libs.

Everything here is glue: unpack a Config into explicit arguments, call a lib,
translate its exception into a DigestError. The libs stay ignorant of config.env
and of how anything is printed.
"""

import sys

import digest_horizon
import digest_podcast
from digest_launchd import LaunchAgent, LaunchdError

from .config import DigestError, die, event, log, need, ok, resolve_date, warn


def agent(cfg):
    return LaunchAgent(cfg.launchd_label)


# -- horizon -----------------------------------------------------------------

def bootstrap(cfg):
    need("git")
    need("uv", "install from https://docs.astral.sh/uv/")
    try:
        digest_horizon.bootstrap(
            horizon_dir=cfg.horizon_dir,
            repo=cfg.get("HORIZON_REPO"),
            pin=cfg.get("HORIZON_PIN"),
            patch=cfg.repo_root / "patches" / "horizon-local.patch",
            seed_config=cfg.repo_root / "config" / "horizon.config.json",
            threshold=cfg.get("HORIZON_THRESHOLD", "5.5"),
            on_event=event,
        )
    except digest_horizon.HorizonError as exc:
        die(str(exc))
    log("Done. Test with: digest run")


def run_daily(cfg, day=None, with_podcast=True):
    """Run Horizon, then optionally the podcast. Returns an exit code."""
    need("uv")
    day = resolve_date(day)
    try:
        status, summary = digest_horizon.run(
            horizon_dir=cfg.horizon_dir, day=day, log_path=cfg.horizon_log,
            env=cfg.env_for_subprocess(), on_event=event,
        )
    except digest_horizon.HorizonError as exc:
        die(str(exc))

    if status != 0:
        warn(f"Horizon failed (exit {status}). Last 20 log lines:")
        print("\n".join(digest_horizon.tail_log(cfg.horizon_log)), file=sys.stderr)
        return status

    ok("Horizon finished")
    ok(f"summary: {summary} ({summary.stat().st_size} bytes)")

    if with_podcast and cfg.flag("PODCAST_ENABLED", True):
        log("Generating podcast")
        try:
            generate_podcast(cfg, day)
        except DigestError as exc:
            # A podcast failure must never fail the digest: the written half is
            # the deliverable and it is already on disk.
            warn(f"podcast generation failed ({exc}) — digest is unaffected")
    return 0


# -- podcast -----------------------------------------------------------------

def install_podcast(cfg):
    try:
        version = digest_podcast.install_venv(cfg.podcast_venv, on_event=event)
    except digest_podcast.PodcastError as exc:
        die(str(exc))
    ok(f"podcastfy {version}")
    ok(f"venv: {cfg.podcast_venv}")


def generate_podcast(cfg, day=None, transcript_only=False):
    try:
        digest_podcast.generate(
            venv_dir=cfg.podcast_venv,
            generator=cfg.generator,
            summary=cfg.summary_path(resolve_date(day)),
            day=resolve_date(day),
            out_dir=cfg.podcast_dir,
            options=cfg.podcast_options(),
            extra=["--transcript-only"] if transcript_only else [],
            env=cfg.env_for_subprocess(),
        )
    except digest_podcast.PodcastError as exc:
        die(str(exc))


def locate_podcast(cfg, day=None):
    return digest_podcast.locate(cfg.podcast_dir, cfg.digests_dir, resolve_date(day))


# -- schedule ----------------------------------------------------------------

def install_schedule(cfg):
    hour, minute = cfg.schedule_time
    job = agent(cfg)
    log(f"Writing {job.path}")
    try:
        # Invoke via this interpreter so the job never depends on which python3
        # happens to be first on launchd's minimal PATH.
        job.install(
            program_args=[sys.executable, cfg.repo_root / "digest", "run"],
            hour=hour, minute=minute,
            stdout=cfg.digest_home / "horizon-stdout.log",
            stderr=cfg.digest_home / "horizon-stderr.log",
        )
    except LaunchdError as exc:
        die(str(exc))
    ok(f"scheduled {cfg.launchd_label} daily at {hour:02d}:{minute:02d}")
    log("Uninstall with: digest uninstall-schedule")


def uninstall_schedule(cfg):
    agent(cfg).uninstall()
    ok(f"removed {cfg.launchd_label}")


def schedule_loaded(cfg):
    return agent(cfg).is_loaded()


def retarget(cfg, old, new, plist_path=None):
    job = LaunchAgent(cfg.launchd_label)
    if plist_path:
        from pathlib import Path
        job.path = Path(plist_path).expanduser()
    try:
        backup = job.retarget(old, new)
    except LaunchdError as exc:
        die(str(exc))
    if backup is None:
        warn(f"no occurrences of {old} in {job.path} — nothing to do")
        return
    ok(f"rewrote {old} → {new}")
    ok(f"backup saved as {backup}")
    log(f"Apply with: launchctl unload {job.path} && launchctl load {job.path}")
