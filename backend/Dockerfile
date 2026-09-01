FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg/asyncpg and image handling.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN mkdir -p src/face_insight && touch src/face_insight/__init__.py
RUN pip install --upgrade pip && pip install .

COPY . .
RUN pip install . --no-deps

EXPOSE 8000

# Default command is overridden by docker-compose to run migrations first.
CMD ["uvicorn", "face_insight.main:app", "--host", "0.0.0.0", "--port", "8000"]
