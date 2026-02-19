# 1. Base Stage: Install common dependencies
FROM python:3.11-slim as base
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Backend Stage: Runs the FastAPI server
FROM base as backend
COPY services/backend/ ./services/backend/
COPY data/ ./data/
EXPOSE 8000
CMD ["uvicorn", "services.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# 3. Bot Stage: Runs the Telegram Bot
FROM base as bot
COPY apps/telegram-bot/ ./apps/telegram-bot/
COPY data/ ./data/
CMD ["python", "apps/telegram-bot/main.py"]