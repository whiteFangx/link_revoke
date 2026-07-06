import asyncio
import logging

from pyrogram import Client, idle

import config
from control_bot import register_control_handlers, userbot_holder
from userbot import build_user_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("main")


async def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is missing in .env — get one from @BotFather first.")
    if not config.OWNER_ID:
        raise SystemExit(
            "OWNER_ID is missing in .env — get your numeric id from @userinfobot. "
            "Required so only you can control this bot."
        )
    if not config.API_ID or not config.API_HASH:
        raise SystemExit(
            "API_ID / API_HASH are missing in .env — get them free from "
            "https://my.telegram.org (API development tools). The control bot "
            "needs these to connect to Telegram at all, so they must be set "
            "before first run (unlike phone/code/password, which /session asks for)."
        )

    control_bot = Client(
        "control_bot_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )
    register_control_handlers(control_bot)
    await control_bot.start()
    log.info("Control bot started. Message it /session on Telegram.")

    if config.SESSION_STRING:
        log.info("Existing SESSION_STRING found — auto-starting userbot...")
        client = build_user_client(config.SESSION_STRING, owner_id=config.OWNER_ID)
        await client.start()
        userbot_holder["client"] = client
        log.info("Userbot active.")

    await idle()

    await control_bot.stop()
    if userbot_holder["client"]:
        await userbot_holder["client"].stop()


if __name__ == "__main__":
    asyncio.run(main())
