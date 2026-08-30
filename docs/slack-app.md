# Slack delivery

The digest posts through its own Slack app rather than a Slack MCP server.

The reason is files. MCP can post messages but cannot upload them, so the daily
podcast could only ever be mentioned as a local path — useless from a phone.
With the app's `files:write` scope the MP3 is attached to the thread and plays
inline. A bot token also removes the routine's dependency on whichever MCP
server happens to be configured in Claude, and on its tool-name prefix.

One-time setup, about five minutes.

## 1. Create the app from the manifest

1. Go to <https://api.slack.com/apps> → **Create New App** → **From a manifest**.
2. Pick the workspace containing your digest channel.
3. Choose **YAML** and paste the output of:

   ```sh
   ./digest slack manifest
   ```

   (the same file as [`slack/manifest.yaml`](../slack/manifest.yaml))
4. Review the scopes → **Create**.

## 2. Install it and copy the bot token

1. **Settings → Install App** → **Install to Workspace**.
2. Approve the permissions. A workspace admin may need to approve this if your
   workspace restricts app installs.
3. Copy the **Bot User OAuth Token** — it starts with `xoxb-`.

## 3. Store the token

The token is a secret and `config.env` is not otherwise sensitive, so keep them
apart. Point `SLACK_TOKEN_FILE` at a file holding just the token:

```sh
umask 077
printf 'SLACK_BOT_TOKEN=xoxb-your-token-here\n' > ~/.config/daily-tech-digest/slack.env
```

```sh
# config.env
SLACK_CHANNEL_ID="C01234567"
SLACK_TOKEN_FILE="${HOME}/.config/daily-tech-digest/slack.env"
```

Resolution order is `--token`, then `$SLACK_BOT_TOKEN`, then `SLACK_BOT_TOKEN`
in `config.env`, then `SLACK_TOKEN_FILE`. Putting `SLACK_BOT_TOKEN` directly in
`config.env` works too — `config.env` is gitignored — but the separate file is
easier to lock down and to rotate.

## 4. Invite the bot to the channel

In Slack, in your digest channel:

```
/invite @Digest
```

Required for uploads and for reading thread history. `chat:write.public` covers
posting alone, but not files and not history.

## 5. Verify

```sh
./digest slack check
```

Expected:

```json
{
  "ok": true,
  "team": "…",
  "bot_user": "digest",
  "channel_id": "C01234567",
  "channel_name": "tech-digest",
  "bot_is_member": true
}
```

If `bot_is_member` is `false`, redo step 4. On `missing_scope`, add the scope
under **OAuth & Permissions** and reinstall — scope changes always require a
reinstall.

---

## The commands the routine uses

Each prints one JSON object on stdout and exits non-zero on failure. On failure
the JSON is `{"ok": false, "error": "..."}`, so a parse never has to guess.

### Post the thread parent

```sh
./digest slack post --text "*🗞️ Daily Tech Digest — August 30, 2026*
38 stories | 4 influencer takes | 🎧 Podcast
_Thread below_ 👇"
# → {"ok": true, "ts": "1756531200.123456", "channel": "C01234567"}
```

That `ts` is the `thread_ts` for every later message, and the value stored as
`slack_thread_ts` in `digests/YYYY-MM-DD/digest.json`.

### Post a thread reply

```sh
./digest slack post --thread-ts 1756531200.123456 --text "⚡ *JS/TS ECOSYSTEM*"
```

For multi-line story messages, pipe instead of quoting — story text routinely
contains backticks, quotes and `$`:

```sh
./digest slack post --thread-ts 1756531200.123456 --text-file - <<'EOF'
*1. Node.js 26 ships stable type stripping*

Native TypeScript execution graduates from experimental. (🔶 412 points)

<https://nodejs.org/blog|Node.js Blog> · <https://news.ycombinator.com/item?id=1|Discussion>
EOF
```

`--no-unfurl` suppresses link previews on link-heavy messages.

### Upload the podcast

```sh
./digest slack upload \
  --file "$(./digest status | awk '/^podcast/{print $3}')" \
  --thread-ts 1756531200.123456 \
  --title "Daily Tech Digest — August 30, 2026" \
  --comment "🎧 *Today's Podcast Episode*"
# → {"ok": true, "file_id": "F0…", "permalink": "https://…", "size_mb": 2.3}
```

Slack renders the MP3 as an inline audio player. This uses Slack's current
three-step external-upload flow (`files.getUploadURLExternal` → PUT the bytes →
`files.completeUploadExternal`); the retired `files.upload` endpoint is not used.

### Read back yesterday's feedback

```sh
./digest slack thread --ts 1756444800.111111       # replies + reactions
./digest slack reactions --ts 1756444800.111111    # one message only
```

`thread` returns every reply with its `reactions` array and an `is_bot` flag, so
one call covers both halves of the feedback step: reactions on story messages,
and replies written by a human rather than by the bot.

## Troubleshooting

| Error | Fix |
| --- | --- |
| `no Slack bot token` | Set `SLACK_TOKEN_FILE` or `SLACK_BOT_TOKEN` — step 3 |
| `not_in_channel` | `/invite @Digest` in the digest channel |
| `missing_scope` | Add the named scope, then reinstall the app |
| `invalid_auth` | Token wrong, revoked, or from another workspace |
| `channel_not_found` | Wrong `SLACK_CHANNEL_ID`, or a private channel the bot isn't in |
| Upload succeeds but no audio | Check the MP3 is non-zero: `./digest status` |

## Rotating the token

Reinstalling the app issues a new `xoxb-` token; replace the contents of your
token file. To revoke, use **OAuth & Permissions → Revoke All OAuth Tokens**, or
delete the app under **Settings → Basic Information → Delete App**.
