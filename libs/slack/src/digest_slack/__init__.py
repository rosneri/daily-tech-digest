"""A small Slack Web API client: post, upload, read threads and reactions.

Deliberately stdlib-only and deliberately narrow — this is the subset the digest
needs, not a general SDK. The one non-obvious piece is `upload_file`, which
implements Slack's three-step external-upload flow; the old single-call
``files.upload`` endpoint was retired in 2025.

Knows nothing about digests: callers pass a token, a channel and text.
"""

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

__all__ = ["SlackClient", "SlackError"]

API = "https://slack.com/api/"


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
    def __init__(self, token, channel=None, timeout=60):
        if not token:
            raise SlackError("client", "no bot token provided")
        self.token = token
        self.channel = channel
        self.timeout = timeout

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
        channel = override or self.channel
        if not channel:
            raise SlackError("client", "no channel specified")
        return channel

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

    def post(self, text, thread_ts=None, channel=None, unfurl=True):
        """Post a message, or a reply when `thread_ts` is given. Returns its ts."""
        payload = {
            "channel": self._channel(channel),
            "text": text,
            "unfurl_links": unfurl,
            "unfurl_media": unfurl,
        }
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


def normalise_reactions(message):
    """Flatten a message's reactions to {name, count, users}."""
    return [
        {"name": r.get("name"), "count": r.get("count"), "users": r.get("users", [])}
        for r in message.get("reactions", [])
    ]
