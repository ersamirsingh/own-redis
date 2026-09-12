FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir .

COPY pyredis/ ./pyredis/
RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/data

EXPOSE 6379 8000

CMD ["python", "-m", "pyredis.main"]
