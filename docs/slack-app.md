# Slack delivery

The digest arrives as a **direct message from the app**, built from Block Kit
blocks, not as a plain-text post in a shared channel.

Two reasons for the app rather than a Slack MCP server. Files: MCP can post
messages but cannot upload them, so the daily podcast could only ever be
mentioned as a local path — useless from a phone. With the app's `files:write`
scope the MP3 is attached to the thread and plays inline. And a bot token
removes the routine's dependency on whichever MCP server happens to be
configured in Claude, and on its tool-name prefix.

The DM is still a real conversation, so nothing about the shape of the digest
changes: the header message is a thread parent, stories are replies, the podcast
uploads into the thread, and the next day's run reads reactions and replies back
out of it. Posting to a channel instead remains supported — see step 3.

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
5. Set the icon. A manifest cannot carry one, so upload it once by hand:
   **Settings → Basic Information → Display Information → App icon** →
   [`slack/icon.png`](../slack/icon.png) (512×512, the source is
   [`slack/icon.svg`](../slack/icon.svg)).

## 2. Install it and copy the bot token

1. **Settings → Install App** → **Install to Workspace**.
2. Approve the permissions. A workspace admin may need to approve this if your
   workspace restricts app installs.
3. Copy the **Bot User OAuth Token** — it starts with `xoxb-`.

## 3. Store the token and pick the destination

The token is a secret and `config.env` is not otherwise sensitive, so keep them
apart. Point `SLACK_TOKEN_FILE` at a file holding just the token:

```sh
mkdir -p ~/.config/daily-tech-digest
umask 077
printf 'SLACK_BOT_TOKEN=xoxb-your-token-here\n' > ~/.config/daily-tech-digest/slack.env
chmod 600 ~/.config/daily-tech-digest/slack.env
```

Then point the digest at yourself. `SLACK_USER_ID` is your own Slack member ID —
in Slack, click your avatar → **Profile** → **⋮** → **Copy member ID**. It starts
with `U`.

```sh
# config.env
SLACK_USER_ID="U01234567"
SLACK_TOKEN_FILE="${HOME}/.config/daily-tech-digest/slack.env"
```

To post to a shared channel instead, leave `SLACK_USER_ID` empty and set
`SLACK_CHANNEL_ID="C01234567"`. A configured user wins over a configured
channel, so an old install keeps working until you add your user ID; after that,
`digest slack --channel C…` (or `$SLACK_CHANNEL_ID` in the environment) is the
one-off override.

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
  "target": "dm",
  "user_id": "U01234567",
  "dm_channel": "D01234567"
}
```

In channel mode the last three keys are `channel_id`, `channel_name` and
`bot_is_member` instead; if `bot_is_member` is `false`, redo step 4. On
`missing_scope`, add the scope under **OAuth & Permissions** and reinstall —
scope changes always require a reinstall.

---

## The commands the routine uses

Each prints one JSON object on stdout and exits non-zero on failure. On failure
the JSON is `{"ok": false, "error": "..."}`, so a parse never has to guess.

### Post the thread parent

Messages are Block Kit. Pipe the JSON in rather than quoting it — story text
routinely contains backticks, quotes and `$`, and a heredoc keeps the shell from
interpreting them:

```sh
./digest slack post --blocks-file - <<'EOF'
[
  {"type": "header",
   "text": {"type": "plain_text", "text": "🗞️  Daily Tech Digest", "emoji": true}},
  {"type": "context",
   "elements": [{"type": "mrkdwn",
                 "text": "*August 30, 2026*  ·  38 stories  ·  4 takes  ·  🎧 Podcast"}]},
  {"type": "divider"}
]
EOF
# → {"ok": true, "ts": "1756531200.123456", "channel": "D01234567"}
```

That `ts` is the `thread_ts` for every later message, and the value stored as
`slack_thread_ts` in `digests/YYYY-MM-DD/digest.json`.

`--blocks-file` also accepts the `{"blocks": [...], "text": "..."}` envelope that
[Block Kit Builder](https://app.slack.com/block-kit-builder) exports, so a
payload can be pasted straight from the builder.

### Post a thread reply

```sh
./digest slack post --thread-ts 1756531200.123456 --blocks-file - <<'EOF'
[
  {"type": "section",
   "text": {"type": "mrkdwn",
            "text": "*1. Node.js 26 ships stable type stripping*\nNative TypeScript execution graduates from experimental."}},
  {"type": "context",
   "elements": [{"type": "mrkdwn",
                 "text": "🔶 412  ·  <https://nodejs.org/blog|Node.js Blog>  ·  <https://news.ycombinator.com/item?id=1|Discussion>"}]}
]
EOF
```

### Notification text

Slack shows `text`, not the blocks, in the push notification and the sidebar
preview — which is most of the value of a DM. Pass it explicitly with `--text`
alongside `--blocks-file`. Without it the first piece of text in the blocks is
used as the fallback, which is usually right for a story and usually wrong for a
header.

Plain mrkdwn still works where blocks would be noise — `--text` or `--text-file`
on their own, e.g. for the failure notice. `--no-unfurl` suppresses link
previews on link-heavy messages.

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
| `not_in_channel` | Channel mode only: `/invite @Digest` in the digest channel |
| `missing_scope: im:write` | Reinstall the app — the DM scopes are new |
| `invalid_blocks` | Block JSON is malformed; check it in Block Kit Builder |
| `too many blocks` | Slack caps a message at 50 blocks — split it |
| `missing_scope` | Add the named scope, then reinstall the app |
| `invalid_auth` | Token wrong, revoked, or from another workspace |
| `channel_not_found` | Wrong `SLACK_CHANNEL_ID`, or a private channel the bot isn't in |
| `user_not_found` | Wrong `SLACK_USER_ID`, or a member of another workspace |
| Upload succeeds but no audio | Check the MP3 is non-zero: `./digest status` |

## Rotating the token

Reinstalling the app issues a new `xoxb-` token; replace the contents of your
token file. To revoke, use **OAuth & Permissions → Revoke All OAuth Tokens**, or
delete the app under **Settings → Basic Information → Delete App**.
