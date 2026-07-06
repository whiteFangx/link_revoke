"""
Control bot — a normal Bot API bot (needs a BOT_TOKEN from @BotFather).
Message it /session and it'll ask you, one by one, for everything needed
to log in as your own account and generate a Pyrogram session string:

    API_ID -> API_HASH -> phone number -> login code -> (2FA password if set)

Once login succeeds, it saves the session string into .env and immediately
starts the userbot in the same process — no restart needed.
"""

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.errors import (
    PhoneCodeInvalid,
    PhoneCodeExpired,
    PasswordHashInvalid,
    SessionPasswordNeeded,
    RPCError,
)
from pyrogram.types import Message

import config
from userbot import build_user_client

log = logging.getLogger("control_bot")

# shared holder so main.py can start/stop the userbot client dynamically
userbot_holder = {"client": None}

# login conversation state (single-owner, so one global state is fine)
state = {"step": None, "api_id": None, "api_hash": None, "phone": None,
         "phone_code_hash": None, "temp_client": None}


def _owner_only(_, __, message: Message):
    if config.OWNER_ID is None:
        return True
    return message.from_user and message.from_user.id == config.OWNER_ID


owner_filter = filters.create(_owner_only)


def _reset_state():
    state.update({"step": None, "api_id": None, "api_hash": None, "phone": None,
                  "phone_code_hash": None, "temp_client": None})


async def _start_userbot_and_notify(message: Message, session_string: str):
    if userbot_holder["client"]:
        try:
            await userbot_holder["client"].stop()
        except Exception:
            pass

    client = build_user_client(session_string, owner_id=config.OWNER_ID)
    await client.start()
    userbot_holder["client"] = client

    await message.reply_text(
        "🚀 **Userbot is now active.**\n\n"
        "Type this yourself, in any chat (Saved Messages, a group, etc.):\n"
        "`/clearlink <chat_id_or_@username>`\n\n"
        "It'll revoke every invite link in that chat and show live progress.\n"
        "Send `/cancel` to stop a running job."
    )


def register_control_handlers(bot: Client):

    @bot.on_message(filters.command("start") & owner_filter)
    async def start_cmd(_, message: Message):
        await message.reply_text(
            "👋 Invite Link Revoker — control bot\n\n"
            "`/session` — log in with your account and activate the userbot\n"
            "`/status` — check if the userbot is active"
        )

    @bot.on_message(filters.command("status") & owner_filter)
    async def status_cmd(_, message: Message):
        active = userbot_holder["client"] is not None
        await message.reply_text("✅ Userbot is active." if active else "⚪ Userbot is not active yet. Send /session.")

    @bot.on_message(filters.command("session") & owner_filter)
    async def session_cmd(_, message: Message):
        _reset_state()
        # API_ID/API_HASH are required just to start this control bot, so they're
        # already loaded — no need to ask again here.
        state["api_id"] = config.API_ID
        state["api_hash"] = config.API_HASH
        state["step"] = "phone"
        await message.reply_text(
            "Let's log in to your account.\n\n"
            "Send your phone number with country code (e.g. `+911234567890`):"
        )

    @bot.on_message(filters.command("cancelsession") & owner_filter)
    async def cancelsession_cmd(_, message: Message):
        if state["temp_client"]:
            try:
                await state["temp_client"].disconnect()
            except Exception:
                pass
        _reset_state()
        await message.reply_text("Login flow cancelled.")

    # Catches plain text replies during the /session conversation
    @bot.on_message(filters.text & owner_filter & ~filters.command(
        ["session", "start", "status", "cancelsession"]))
    async def conversation_step(_, message: Message):
        step = state["step"]
        if step is None:
            return  # not in a /session flow, ignore

        text = message.text.strip()

        try:
            if step == "phone":
                state["phone"] = text
                client = Client(
                    "login_temp",
                    api_id=state["api_id"],
                    api_hash=state["api_hash"],
                    in_memory=True,
                )
                await client.connect()
                sent = await client.send_code(state["phone"])
                state["phone_code_hash"] = sent.phone_code_hash
                state["temp_client"] = client
                state["step"] = "code"
                await message.reply_text(
                    "Telegram sent you a login code. Enter it here.\n\n"
                    "⚠️ Type the digits with a space between them (e.g. `1 2 3 4 5`) "
                    "— Telegram auto-invalidates codes that look unmodified when sent "
                    "to another chat/bot."
                )

            elif step == "code":
                code = text.replace(" ", "")
                client = state["temp_client"]
                try:
                    await client.sign_in(state["phone"], state["phone_code_hash"], code)
                except SessionPasswordNeeded:
                    state["step"] = "password"
                    await message.reply_text("You have 2FA enabled. Send your **2FA password**:")
                    return
                except (PhoneCodeInvalid, PhoneCodeExpired):
                    await message.reply_text("❌ Invalid/expired code. Send /session to start over.")
                    _reset_state()
                    return

                session_string = await client.export_session_string()
                await client.disconnect()
                config.persist(
                    API_ID=state["api_id"], API_HASH=state["api_hash"],
                    SESSION_STRING=session_string,
                )
                _reset_state()
                await message.reply_text("✅ Logged in! Saving session and starting userbot...")
                await _start_userbot_and_notify(message, session_string)

            elif step == "password":
                client = state["temp_client"]
                try:
                    await client.check_password(text)
                except PasswordHashInvalid:
                    await message.reply_text("❌ Wrong password. Try again, or /cancelsession to abort.")
                    return

                session_string = await client.export_session_string()
                await client.disconnect()
                config.persist(
                    API_ID=state["api_id"], API_HASH=state["api_hash"],
                    SESSION_STRING=session_string,
                )
                _reset_state()
                await message.reply_text("✅ Logged in! Saving session and starting userbot...")
                await _start_userbot_and_notify(message, session_string)

        except RPCError as e:
            await message.reply_text(f"❌ Telegram error: `{e}`\nSend /session to start over.")
            _reset_state()
