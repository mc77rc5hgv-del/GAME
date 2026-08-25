FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY avito_client.py avito_categories.py db.py bot.py ./

# No VOLUME instruction here: Railway doesn't support it in Dockerfiles.
# Persistence is provided by a Railway Volume mounted at /app/bot instead
# (configure it in the service's Settings -> Volumes).
ENV AVITO_BOT_DB=/app/bot/avito_bot.db

CMD ["python", "bot.py"]
