"""A small Slack Web API client: post, upload, read threads and reactions.

Deliberately stdlib-only and deliberately narrow — this is the subset the digest
needs, not a general SDK. The one non-obvious piece is `upload_file`, which
implements Slack's three-step external-upload flow; the old single-call
``files.upload`` endpoint was retired in 2025.

The default delivery target is a DM with the user rather than a channel: given a
`user`, the client opens the bot's IM conversation once and treats that as its
channel, so posting, uploading and reading threads all work unchanged.

Knows nothing about digests: callers pass a token, a destination and content.
"""

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

__all__ = ["SlackClient", "SlackError", "fallback_text", "normalise_reactions"]

API = "https://slack.com/api/"

# Slack rejects a message carrying more than this many blocks.
MAX_BLOCKS = 50


class SlackError(Exception):
    """A Slack API call returned ok=false, or the transport failed.

    `error` carries Slack's own machine-readable code (``not_in_channel``,
    ``missing_scope``, …) so callers can branch on it rather than on prose.
    """

    def __init__(self, method, error, needed=None):
        self.method = method
        self.error = error
        self.needed = needed
        detail = f"{method}: {error}"
        if needed:
            detail += f" (missing scope: {needed})"
        super().__init__(detail)


class SlackClient:
    def __init__(self, token, channel=None, user=None, timeout=60):
        if not token:
            raise SlackError("client", "no bot token provided")
        self.token = token
        self.channel = channel
        self.user = user
        self.timeout = timeout
        self._dm = None

    # -- plumbing ------------------------------------------------------------

    def call(self, method, payload=None, params=None):
        """Invoke a Web API method. GET with `params`, JSON POST with `payload`."""
        url = API + method
        headers = {"Authorization": f"Bearer {self.token}"}
        if params is not None:
            url += "?" + urllib.parse.urlencode(params)
            data = None
        else:
            data = json.dumps(payload or {}).encode()
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode())
        except urllib.error.URLError as exc:
            raise SlackError(method, f"request failed — {exc}") from exc

        if not body.get("ok"):
            raise SlackError(method, body.get("error", "unknown_error"), body.get("needed"))
        return body

    def _channel(self, override=None):
        """Resolve the destination: an explicit one, the channel, else the DM.

        The DM id is fetched once and reused — conversations.open is idempotent,
        but a digest run posts dozens of messages and one lookup is enough.
        """
        channel = override or self.channel
        if channel:
            return channel
        if self.user:
            return self.open_dm()
        raise SlackError("client", "no channel or user specified")

    def open_dm(self, user=None):
        """Return the id of the bot's IM conversation with `user`."""
        user = user or self.user
        if not user:
            raise SlackError("conversations.open", "no user specified")
        if user == self.user and self._dm:
            return self._dm
        dm = self.call("conversations.open", {"users": user})["channel"]["id"]
        if user == self.user:
            self._dm = dm
        return dm

    # -- reads ---------------------------------------------------------------

    def auth_test(self):
        return self.call("auth.test")

    def channel_info(self, channel=None):
        return self.call("conversations.info",
                         params={"channel": self._channel(channel)})["channel"]

    def read_thread(self, ts, channel=None, limit=300):
        """Return a thread's messages, each with its reactions already attached.

        One call covers both feedback signals — emoji and replies — so callers
        do not have to fan out a reactions.get per message.
        """
        body = self.call("conversations.replies", params={
            "channel": self._channel(channel), "ts": ts, "limit": limit,
        })
        return [
            {
                "ts": m.get("ts"),
                "user": m.get("user"),
                "is_bot": bool(m.get("bot_id")),
                "text": m.get("text", ""),
                "reactions": normalise_reactions(m),
            }
            for m in body.get("messages", [])
        ]

    def reactions(self, ts, channel=None):
        body = self.call("reactions.get", params={
            "channel": self._channel(channel), "timestamp": ts, "full": "true",
        })
        return normalise_reactions(body.get("message", {}))

    # -- writes --------------------------------------------------------------

    def post(self, text=None, blocks=None, thread_ts=None, channel=None, unfurl=True):
        """Post a message, or a reply when `thread_ts` is given. Returns its ts.

        `blocks` is Block Kit. `text` stays required alongside it — Slack uses it
        for the push notification and the sidebar preview, which is the whole
        point of a DM — so it is derived from the blocks when not supplied.
        """
        if blocks is not None:
            if not isinstance(blocks, list):
                raise SlackError("chat.postMessage", "blocks must be a JSON array")
            if not blocks:
                raise SlackError("chat.postMessage", "blocks is empty")
            if len(blocks) > MAX_BLOCKS:
                raise SlackError("chat.postMessage",
                                 f"too many blocks: {len(blocks)} > {MAX_BLOCKS}")
            text = text or fallback_text(blocks)
        elif not text:
            raise SlackError("chat.postMessage", "no text and no blocks")

        payload = {
            "channel": self._channel(channel),
            "text": text,
            "unfurl_links": unfurl,
            "unfurl_media": unfurl,
        }
        if blocks is not None:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
        body = self.call("chat.postMessage", payload)
        return {"ts": body["ts"], "channel": body["channel"]}

    def upload_file(self, path, title=None, comment=None, thread_ts=None, channel=None):
        """Upload a file and share it into a channel or thread.

        Three steps, per Slack's current API: reserve a URL, PUT the bytes to it
        (that host is not the Web API and takes no bearer token), then complete
        the upload to actually share it.
        """
        path = Path(path).expanduser()
        if not path.is_file():
            raise SlackError("upload", f"file not found: {path}")
        size = path.stat().st_size
        if size == 0:
            raise SlackError("upload", f"file is empty: {path}")

        reserved = self.call("files.getUploadURLExternal",
                             params={"filename": path.name, "length": size})
        self._put_bytes(reserved["upload_url"], path)

        payload = {
            "files": [{"id": reserved["file_id"], "title": title or path.name}],
            "channel_id": self._channel(channel),
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts
        if comment:
            payload["initial_comment"] = comment

        uploaded = (self.call("files.completeUploadExternal", payload).get("files") or [{}])[0]
        return {
            "file_id": uploaded.get("id"),
            "permalink": uploaded.get("permalink"),
            "size_mb": round(size / 1_000_000, 1),
        }

    def _put_bytes(self, upload_url, path):
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

        request = urllib.request.Request(
            upload_url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            # Large MP3s over a slow uplink: allow well past the API timeout.
            with urllib.request.urlopen(request, timeout=max(self.timeout, 300)) as response:
                response.read()
        except urllib.error.URLError as exc:
            raise SlackError("upload", f"upload failed — {exc}") from exc


def fallback_text(blocks):
    """Best-effort notification text for a Block Kit message.

    Slack shows this in the push notification and the channel list, so an empty
    string would make a DM digest arrive as a silent, unlabelled blob. Take the
    first piece of human text in the blocks; a caller that cares passes its own.
    """
    for block in blocks:
        if not isinstance(block, dict):
            continue
        candidates = [block.get("text")] + list(block.get("fields") or [])
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("text", "").strip():
                return candidate["text"].strip().splitlines()[0][:150]
    return "Daily Tech Digest"


def normalise_reactions(message):
    """Flatten a message's reactions to {name, count, users}."""
    return [
        {"name": r.get("name"), "count": r.get("count"), "users": r.get("users", [])}
        for r in message.get("reactions", [])
    ]
