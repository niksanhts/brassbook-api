FROM python:3.9-slim
WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 && \
    pip install --no-cache-dir -r requirements.txt uvicorn && \
    rm -rf /var/lib/apt/lists/*

# Копируем приложение
COPY . .

EXPOSE 8000
ENTRYPOINT ["sh", "-c", "alembic revision --autogenerate && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]