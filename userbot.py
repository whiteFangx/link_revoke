"""
The userbot: runs AS your own Telegram account (via a Pyrogram session
string), because only a real user account with admin rights can see and
revoke every invite link in a chat — the primary/permanent link, and links
made by other admins. A normal Bot API bot can only see links it made itself.

Commands (type these yourself, in ANY chat — Saved Messages, a group, a DM —
since this account IS the userbot):

    /clearlink <chat_id_or_@username>   — revoke every invite link in that chat
    /cancel                              — stop an in-progress job
"""

import asyncio
import logging
import time

from pyrogram import Client, filters
from pyrogram.errors import (
    FloodWait,
    ChatAdminRequired,
    ChatAdminInviteRequired,
    RPCError,
)
from pyrogram.types import Message

log = logging.getLogger("userbot")

EDIT_EVERY_N = 5
EDIT_EVERY_SECS = 2.5
SLEEP_BETWEEN_REVOKES = 0.6

# One job at a time; lets /cancel stop it cleanly.
_job = {"task": None, "cancel": False}


def _me_only(owner_id):
    """Only react to messages sent by the account itself (typed by you,
    anywhere), and optionally double-checked against your known owner id."""
    async def check(_, __, message: Message):
        if not message.outgoing:
            return False
        if owner_id and message.from_user and message.from_user.id != owner_id:
            return False
        return True
    return filters.create(check)


async def _collect_all_invite_links(client: Client, chat_id):
    links = {}  # invite_link string -> admin_id (or None for primary)

    chat = await client.get_chat(chat_id)
    if chat.invite_link:
        links[chat.invite_link] = None

    try:
        async for member in client.get_chat_members(chat_id, filter="administrators"):
            admin_id = member.user.id
            try:
                async for invite in client.get_chat_invite_links(
                    chat_id, admin_id=admin_id, revoked=False
                ):
                    links[invite.invite_link] = admin_id
            except (ChatAdminRequired, ChatAdminInviteRequired):
                continue
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except RPCError:
                continue
    except (ChatAdminRequired, ChatAdminInviteRequired):
        pass

    return links


async def _do_revoke_job(client: Client, status_msg: Message, chat_id):
    _job["cancel"] = False
    try:
        await status_msg.edit_text(f"🔎 Scanning `{chat_id}` for invite links...")
    except RPCError:
        pass

    try:
        links = await _collect_all_invite_links(client, chat_id)
    except RPCError as e:
        await status_msg.edit_text(f"❌ Couldn't read invite links: `{e}`")
        return

    total = len(links)
    if total == 0:
        await status_msg.edit_text("✅ No invite links found — nothing to revoke.")
        return

    done, failed = 0, 0
    last_edit = 0.0
    await status_msg.edit_text(f"🚨 Found **{total}** invite link(s). Starting revoke...\n\n0/{total}")

    for invite_link, admin_id in links.items():
        if _job["cancel"]:
            await status_msg.edit_text(f"🛑 Cancelled.\n\nRevoked: {done}/{total}\nFailed: {failed}")
            return

        try:
            await client.revoke_chat_invite_link(chat_id, invite_link)
            done += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.revoke_chat_invite_link(chat_id, invite_link)
                done += 1
            except RPCError:
                failed += 1
        except RPCError as e:
            log.warning(f"Failed to revoke {invite_link}: {e}")
            failed += 1

        now = time.time()
        if (done + failed) % EDIT_EVERY_N == 0 or (now - last_edit) > EDIT_EVERY_SECS:
            last_edit = now
            try:
                await status_msg.edit_text(
                    f"⏳ Revoking invite links...\n\n"
                    f"Progress: {done + failed}/{total}\n"
                    f"✅ Revoked: {done}   ❌ Failed: {failed}"
                )
            except RPCError:
                pass

        await asyncio.sleep(SLEEP_BETWEEN_REVOKES)

    await status_msg.edit_text(
        f"✅ **Done.**\n\nTotal found: {total}\nRevoked: {done}\nFailed: {failed}"
    )


def build_user_client(session_string: str, owner_id=None) -> Client:
    """Create (but don't start) the userbot Client with /clearlink + /cancel wired up."""
    client = Client("userbot_session", session_string=session_string, in_memory=True)
    me_only = _me_only(owner_id)

    @client.on_message(filters.command("clearlink", prefixes="/") & me_only)
    async def clearlink_cmd(c: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/clearlink <chat_id_or_@username>`")
            return
        if _job["task"] and not _job["task"].done():
            await message.reply_text("⚠️ A revoke job is already running. Send /cancel first.")
            return

        target = message.command[1]
        try:
            target_parsed = int(target)
        except ValueError:
            target_parsed = target

        status_msg = await message.reply_text(f"Preparing to revoke invite links for `{target}`...")
        _job["task"] = asyncio.create_task(_do_revoke_job(c, status_msg, target_parsed))

    @client.on_message(filters.command("cancel", prefixes="/") & me_only)
    async def cancel_cmd(c: Client, message: Message):
        if _job["task"] and not _job["task"].done():
            _job["cancel"] = True
            await message.reply_text("Cancelling after current link finishes...")
        else:
            await message.reply_text("No revoke job is running.")

    return client
