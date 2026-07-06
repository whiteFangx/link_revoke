# Invite Link Clearer (control bot + userbot, all-in-one)

Revokes **every** invite link in a Telegram channel/group — including the
primary/permanent link and links made by other admins, not just links a
bot itself created.

## Why two bots in one project?

- Telegram's **Bot API** only lets a bot see/revoke invite links it created
  itself. There's no way for a normal bot to see the primary link or other
  admins' links.
- Seeing/revoking *everything* requires the full MTProto client API, logged
  in as a real user account with admin rights in the target chat.

So this project has:
1. **Control bot** (`BOT_TOKEN`, normal Bot API) — you message it `/session`
   and it walks you through logging in with your own account, step by step,
   right inside the chat.
2. **Userbot** — once login succeeds, it activates automatically in the same
   process, running as your account. You then type `/clearlink <chat_id>`
   **yourself**, anywhere (Saved Messages, a group, a DM) — since it's your
   own account, Telegram sees it as a message you sent, and the userbot
   reacts to it.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Get a free `API_ID` + `API_HASH` from https://my.telegram.org
   (log in → API development tools → create an app). These are required
   just to start the control bot — Telegram ties every connection, bot or
   user, to an app's API_ID/API_HASH.

3. Create a bot with **@BotFather** on Telegram, get its `BOT_TOKEN`.

4. Get your own numeric Telegram ID from **@userinfobot**.

5. Copy `.env.example` → `.env` and fill in `API_ID`, `API_HASH`,
   `BOT_TOKEN`, `OWNER_ID`. Leave `SESSION_STRING` blank.

6. Run it:
   ```
   python main.py
   ```

## First-time login

1. Open a DM with your control bot on Telegram, send `/session`.
2. It asks for your **phone number** (with country code, e.g. `+911234567890`).
3. Telegram texts you a login code. Enter it in the chat with a space
   between each digit (e.g. `1 2 3 4 5`) — Telegram auto-invalidates codes
   that look like they were copy-pasted unmodified into another chat/bot.
4. If you have 2FA enabled, it'll ask for your password too.
5. On success, it saves the session into `.env` and **immediately activates
   the userbot** — no restart needed.

On future restarts, since `SESSION_STRING` is already saved, the userbot
activates automatically and you don't need `/session` again.

## Usage

Once active, type this **yourself**, in any chat:

```
/clearlink <chat_id_or_@username>
```

Examples:
```
/clearlink @mychannelusername
/clearlink -1001234567890
```

You'll see a live-updating progress message:

```
⏳ Revoking invite links...

Progress: 15/42
✅ Revoked: 14   ❌ Failed: 1
```

Send `/cancel` (yourself, anywhere) to stop an in-progress job.

## Control bot commands (DM the bot with these)

- `/session` — start the login flow
- `/status` — check whether the userbot is currently active
- `/cancelsession` — abort an in-progress login flow

## Deploying on Coolify

This runs as a **background worker** (it long-polls Telegram — no HTTP
server, no port to expose), so a couple of Coolify-specific tweaks matter.

1. **Push this project to a Git repo** (GitHub/GitLab/etc.) — Coolify deploys
   from a repo, not a local zip.

2. In Coolify: **New Resource → Docker Compose** (recommended, since
   `docker-compose.yml` is already set up with the persistent volume), point
   it at your repo.
   - Alternatively: **New Resource → Application → Dockerfile**, same repo.

3. **Set environment variables** in the Coolify UI (Environment Variables
   tab) instead of committing a real `.env`:
   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
   - `OWNER_ID`
   - Leave `SESSION_STRING` empty at first.

4. **Disable the HTTP health check / port requirement.** Since there's no
   web server here, in the resource's settings turn off "Health Check" (or
   set it to a simple process check) and don't map any port — otherwise
   Coolify may keep restarting the container thinking it's unhealthy.

5. **Make sure the volume persists.** With the provided `docker-compose.yml`,
   `/app/data` is a named volume — this is where `/session` saves your
   `SESSION_STRING` after login, so it survives restarts and redeploys.
   Don't delete this volume unless you want to log in again from scratch.

6. **Deploy.** Check the Coolify logs — you should see
   `Control bot started. Message it /session on Telegram.`

7. DM your control bot on Telegram, send `/session`, complete the login
   flow as described above. Once it says the userbot is active, you're done
   — redeploys/restarts after this will auto-reuse the saved session.



- You need to be an **admin with "Invite Users via Link" rights** (or the
  creator) in the target chat — otherwise the account can't see other
  admins' links, and some may get skipped rather than crash the job.
- Large chats with hundreds of links just take longer; the script paces
  itself (~0.6s between revokes) and handles Telegram's FloodWait
  automatically.
- Keep your `.env` private — `SESSION_STRING` is equivalent to being logged
  into your Telegram account. Don't commit it or share the filled-in file.
- This is a long-running script (`python main.py` keeps listening). Run it
  in a terminal, `screen`/`tmux`, or as a background service if you want it
  always-on.
