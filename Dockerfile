FROM python:3.9 AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /venv
RUN /venv/bin/pip install --upgrade pip
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.9

WORKDIR /app
COPY --from=builder /venv /venv
COPY . .

# Устанавливаем libmagic
RUN apt-get update && apt-get install -y libmagic-dev

ENV PATH="/venv/bin:$PATH"

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"]
