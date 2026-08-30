"""The `digest slack` subcommand: the CLI surface over digest_slack.

Each command prints one JSON object on stdout, including on failure, because
the Claude routine parses that output and should never have to guess.
"""

import json
import sys
from pathlib import Path

from digest_slack import SlackClient, SlackError

from .config import DigestError, die, load_config


def _client(args):
    cfg = load_config()
    token = cfg.slack_token(getattr(args, "token", None))
    if not token:
        die("no Slack bot token — set SLACK_BOT_TOKEN in the environment or "
            "config.env, or point SLACK_TOKEN_FILE at a file, see docs/slack-app.md")
    channel = cfg.slack_channel(getattr(args, "channel", None))
    if not channel:
        die("no Slack channel — set SLACK_CHANNEL_ID in config.env")
    return SlackClient(token, channel), cfg


def _emit(payload):
    print(json.dumps(payload, indent=2 if len(payload) > 3 else None))


def _read_text(args):
    if args.text_file:
        if args.text_file == "-":
            return sys.stdin.read().rstrip("\n")
        return Path(args.text_file).read_text().rstrip("\n")
    if args.text is None:
        die("provide --text or --text-file")
    return args.text


def cmd_check(args):
    client, _ = _client(args)
    auth = client.auth_test()
    info = client.channel_info()
    _emit({
        "ok": True,
        "team": auth.get("team"),
        "bot_user": auth.get("user"),
        "channel_id": client.channel,
        "channel_name": info.get("name"),
        "bot_is_member": info.get("is_member", False),
    })


def cmd_post(args):
    client, _ = _client(args)
    result = client.post(_read_text(args), thread_ts=args.thread_ts,
                         unfurl=not args.no_unfurl)
    _emit({"ok": True, **result})


def cmd_upload(args):
    client, _ = _client(args)
    result = client.upload_file(args.file, title=args.title, comment=args.comment,
                                thread_ts=args.thread_ts)
    _emit({"ok": True, **result})


def cmd_thread(args):
    client, _ = _client(args)
    _emit({"ok": True, "messages": client.read_thread(args.ts)})


def cmd_reactions(args):
    client, _ = _client(args)
    _emit({"ok": True, "ts": args.ts, "reactions": client.reactions(args.ts)})


def cmd_manifest(args):
    from .config import REPO_ROOT
    print((REPO_ROOT / "slack" / "manifest.yaml").read_text(), end="")


def add_parser(sub):
    slack = sub.add_parser("slack", help="post the digest via the Slack app")
    slack.add_argument("--token", help="bot token (default: env, config.env, token file)")
    slack.add_argument("--channel", help="channel ID (default: SLACK_CHANNEL_ID)")
    ops = slack.add_subparsers(dest="slack_command", required=True)

    ops.add_parser("check", help="verify token, scopes and channel membership")
    ops.add_parser("manifest", help="print slack/manifest.yaml")

    p = ops.add_parser("post", help="send a message or thread reply")
    p.add_argument("--text", help="message text (Slack mrkdwn)")
    p.add_argument("--text-file", help="read text from a file, or - for stdin")
    p.add_argument("--thread-ts", help="reply in this thread")
    p.add_argument("--no-unfurl", action="store_true", help="disable link previews")

    p = ops.add_parser("upload", help="upload a file, e.g. the podcast MP3")
    p.add_argument("--file", required=True)
    p.add_argument("--title", help="file title shown in Slack")
    p.add_argument("--comment", help="message posted alongside the file")
    p.add_argument("--thread-ts", help="upload into this thread")

    p = ops.add_parser("thread", help="read a thread with per-message reactions")
    p.add_argument("--ts", required=True, help="parent message ts")

    p = ops.add_parser("reactions", help="read reactions on one message")
    p.add_argument("--ts", required=True)


def dispatch(args):
    handler = {
        "check": cmd_check, "post": cmd_post, "upload": cmd_upload,
        "thread": cmd_thread, "reactions": cmd_reactions, "manifest": cmd_manifest,
    }[args.slack_command]
    try:
        handler(args)
    except SlackError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "slack_error": exc.error}))
        die(str(exc))
    except DigestError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise
