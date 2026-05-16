FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY botox_session_ledger.py .
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/

EXPOSE 8000

# Run migrations then start the server
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
