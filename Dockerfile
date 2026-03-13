FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY defend_api ./defend_api

ENV DEFEND_API_HOST=0.0.0.0 \
    DEFEND_API_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "defend_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

