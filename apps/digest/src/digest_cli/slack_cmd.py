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
    channel, user = cfg.slack_target(getattr(args, "channel", None),
                                     getattr(args, "user", None))
    return SlackClient(token, channel or None, user or None), cfg


def _emit(payload):
    print(json.dumps(payload, indent=2 if len(payload) > 3 else None))


def _slurp(source):
    """Read a --*-file argument: `-` means stdin."""
    if source == "-":
        return sys.stdin.read()
    return Path(source).expanduser().read_text()


def _read_text(args):
    if args.text_file:
        return _slurp(args.text_file).rstrip("\n")
    return args.text


def _read_blocks(args):
    """Parse --blocks/--blocks-file into a Block Kit array.

    Accepts either a bare array of blocks or the `{"blocks": [...], "text": ...}`
    envelope that Block Kit Builder exports, so payloads can be pasted straight
    from the builder without being unwrapped first.
    """
    raw = _slurp(args.blocks_file) if args.blocks_file else args.blocks
    if raw is None:
        return None, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        die(f"--blocks is not valid JSON: {exc}")
    if isinstance(payload, dict):
        blocks = payload.get("blocks")
        if blocks is None:
            die('block JSON object has no "blocks" key')
        return blocks, payload.get("text")
    return payload, None


def cmd_check(args):
    client, _ = _client(args)
    auth = client.auth_test()
    result = {"ok": True, "team": auth.get("team"), "bot_user": auth.get("user")}

    if client.channel:
        # A channel still has to be joined; a DM the bot opened never does.
        info = client.channel_info()
        result.update(target="channel", channel_id=client.channel,
                      channel_name=info.get("name"),
                      bot_is_member=info.get("is_member", False))
    else:
        result.update(target="dm", user_id=client.user, dm_channel=client.open_dm())
    _emit(result)


def cmd_post(args):
    client, _ = _client(args)
    blocks, block_text = _read_blocks(args)
    text = _read_text(args) or block_text
    if blocks is None and text is None:
        die("provide --text, --text-file, --blocks or --blocks-file")
    result = client.post(text, blocks=blocks, thread_ts=args.thread_ts,
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
    slack.add_argument("--user", help="DM this user ID (default: SLACK_USER_ID)")
    slack.add_argument("--channel", help="post to this channel ID instead of the DM")
    ops = slack.add_subparsers(dest="slack_command", required=True)

    ops.add_parser("check", help="verify token, scopes and channel membership")
    ops.add_parser("manifest", help="print slack/manifest.yaml")

    p = ops.add_parser("post", help="send a message or thread reply")
    p.add_argument("--text", help="message text (Slack mrkdwn), or the "
                                  "notification fallback when --blocks is used")
    p.add_argument("--text-file", help="read text from a file, or - for stdin")
    p.add_argument("--blocks", help="Block Kit JSON array (or a {blocks:[...]} object)")
    p.add_argument("--blocks-file", help="read block JSON from a file, or - for stdin")
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
