FROM python:3.11-slim

WORKDIR /app

# Install timezone data and system packages if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone (change to your timezone)
ENV TZ=Europe/Kyiv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot

# SQLite database will be stored in /app/data/bot.db
# We can create this directory to mount it as a volume
RUN mkdir -p /app/data

# We configure the environment to point SQLite to the volume if needed,
# or we can run the bot in the root. By default, engine.py uses "sqlite+aiosqlite:///bot.db".
# If we run from /app, bot.db will be in /app/bot.db. We can mount the file or the entire /app.
# For simplicity, we can mount a volume to /app/data and update the path, but let's keep it in /app
# and the user can mount the specific file or folder.

CMD ["python", "-m", "bot.main"]
