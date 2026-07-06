import os
from dotenv import load_dotenv

# DATA_DIR is where persistent state lives. In Docker/Coolify, mount a volume
# here (e.g. ./data:/app/data) so SESSION_STRING survives restarts/redeploys.
# Locally (no Docker), it just falls back to the project folder.
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)

ENV_PATH = os.path.join(DATA_DIR, ".env")
LOCAL_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# Load persisted env first (if it exists from a previous /session run),
# then the project .env (for first-run values like BOT_TOKEN/API_ID/API_HASH),
# without overriding anything already loaded.
load_dotenv(ENV_PATH)
load_dotenv(LOCAL_ENV_PATH)

# Control bot (Bot API) — talk to this one to run /session
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Your Telegram numeric user ID. ONLY this user can use /session, /clearlink, /cancel*.
# Get it from @userinfobot. This is required — without it, anyone who messages
# your control bot could hijack the login flow.
_owner = os.getenv("OWNER_ID", "").strip()
OWNER_ID = int(_owner) if _owner else None

# These can be pre-filled, or left blank and entered during /session.
_api_id = os.getenv("API_ID", "").strip()
API_ID = int(_api_id) if _api_id else None
API_HASH = os.getenv("API_HASH", "").strip() or None

# Filled in automatically by /session once login succeeds. If already present,
# the userbot auto-starts on launch without needing /session again.
SESSION_STRING = os.getenv("SESSION_STRING", "").strip() or None


def persist(**kwargs):
    """Write/update key=value pairs into the persistent .env (under DATA_DIR)
    so they survive container restarts/redeploys when DATA_DIR is a mounted volume."""
    from dotenv import set_key
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH, "a").close()
    for key, value in kwargs.items():
        set_key(ENV_PATH, key, str(value))

