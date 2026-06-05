FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

RUN python -m compileall -q . 2>/dev/null || true

EXPOSE 8000

CMD python manage.py migrate --settings=config.settings.production && \
    daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application