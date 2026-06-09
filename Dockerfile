FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY backend ./backend
COPY frontend ./frontend

EXPOSE 10000

CMD ["sh", "-c", "python backend/migrate.py && gunicorn --chdir backend --bind 0.0.0.0:${PORT} app:app"]
