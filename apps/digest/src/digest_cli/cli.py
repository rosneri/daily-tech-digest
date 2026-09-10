"""Command-line entry point.

The only client of the libs. Everything here is argument parsing and dispatch;
the behaviour lives in libs/ and the wiring in commands.py.
"""

import argparse
import sys

from . import commands, deliver, install, slack_cmd, status
from .config import DigestError, load_config


def build_parser():
    parser = argparse.ArgumentParser(
        prog="digest",
        description="Daily Tech Digest — automated morning tech briefing.",
        epilog="Override the date on any dated command:  digest podcast --date 2026-08-28",
    )
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("install", help="full install (horizon + podcast + schedule)")
    p.add_argument("--no-podcast", action="store_true", help="skip podcastfy")
    p.add_argument("--no-schedule", action="store_true", help="skip the launchd job")

    sub.add_parser("config", help="create config.env from the example")
    sub.add_parser("install-podcast", help="install podcastfy into its own venv")
    sub.add_parser("install-schedule", help="install/reload the daily launchd job")
    sub.add_parser("uninstall-schedule", help="remove the launchd job")

    p = sub.add_parser("run", help="the whole morning: Horizon, podcast, deliver")
    p.add_argument("--no-podcast", action="store_true",
                   help="skip podcast generation after the summary")
    p.add_argument("--no-deliver", action="store_true",
                   help="stop after Horizon and the podcast; do not post")

    p = sub.add_parser("deliver", help="compose and DM the digest for the date")
    p.add_argument("--dry-run", action="store_true",
                   help="print the Block Kit messages instead of sending them")

    sub.add_parser("bootstrap", help="clone/patch Horizon without a full install")

    p = sub.add_parser("podcast", help="generate the podcast episode")
    p.add_argument("--transcript-only", action="store_true",
                   help="write the script without synthesising audio")

    sub.add_parser("status", help="show what exists for the date")
    p = sub.add_parser("logs", help="tail the Horizon log")
    p.add_argument("-n", type=int, default=40, help="lines to show")
    sub.add_parser("summary", help="print the summary headlines for the date")
    sub.add_parser("check", help="verify config, dependencies and syntax")
    sub.add_parser("test", help="run the test suite")

    p = sub.add_parser("clean", help="remove generated podcast artefacts")
    p.add_argument("--yes", action="store_true", help="actually delete")

    p = sub.add_parser("retarget", help="rewrite paths inside an installed plist")
    p.add_argument("--old", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--plist", help="plist path (default: the configured job)")

    slack_cmd.add_parser(sub)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    # `config` and `slack manifest` must work before config.env exists.
    if args.command == "config":
        if install.create_config():
            print("created config.env — edit it before installing")
        else:
            print("config.env already exists")
        return 0
    if args.command == "slack" and args.slack_command == "manifest":
        return slack_cmd.dispatch(args) or 0

    if args.command == "install":
        install.install(with_podcast=not args.no_podcast,
                        with_schedule=not args.no_schedule)
        return 0

    cfg = load_config()

    if args.command == "run":
        return commands.run_daily(cfg, args.date, with_podcast=not args.no_podcast,
                                  with_delivery=not args.no_deliver)
    if args.command == "deliver":
        return deliver.deliver(cfg, args.date, dry_run=args.dry_run)
    if args.command == "bootstrap":
        commands.bootstrap(cfg)
    elif args.command == "install-podcast":
        commands.install_podcast(cfg)
    elif args.command == "install-schedule":
        commands.install_schedule(cfg)
    elif args.command == "uninstall-schedule":
        commands.uninstall_schedule(cfg)
    elif args.command == "podcast":
        commands.generate_podcast(cfg, args.date, args.transcript_only)
    elif args.command == "status":
        status.status(cfg, args.date)
    elif args.command == "logs":
        status.logs(cfg, args.n)
    elif args.command == "summary":
        status.summary(cfg, args.date)
    elif args.command == "check":
        return status.check(cfg)
    elif args.command == "test":
        return status.test()
    elif args.command == "clean":
        status.clean(cfg, args.yes)
    elif args.command == "retarget":
        commands.retarget(cfg, args.old, args.new, args.plist)
    elif args.command == "slack":
        slack_cmd.dispatch(args)
    return 0


def entry():
    try:
        sys.exit(main() or 0)
    except DigestError as exc:
        print(f"\033[0;31merror:\033[0m {exc}" if sys.stderr.isatty() else f"error: {exc}",
              file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
