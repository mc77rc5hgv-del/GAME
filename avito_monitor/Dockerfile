FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY avito_client.py db.py bot.py ./

VOLUME ["/app/bot"]
ENV AVITO_BOT_DB=/app/bot/avito_bot.db

CMD ["python", "bot.py"]
