FROM python:3.11-slim

# tgcrypto needs a C compiler to build from source on some architectures
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent state (the auto-generated SESSION_STRING etc.) lives here.
# Mount a volume to this path in docker-compose / Coolify so it survives
# container restarts and redeploys.
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data

# No HTTP port — this is a background worker (long-polling Telegram),
# not a web service. If your platform requires a port/health check,
# see README.md for how to disable it.

CMD ["python", "main.py"]
