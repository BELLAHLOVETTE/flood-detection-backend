FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy all application code
COPY . .

# Collect static files for production
RUN python manage.py collectstatic --noinput \
    --settings=config.settings.production \
    || true

# Expose port
EXPOSE 8000

# Start command — migrate then start daphne
CMD sh -c "python manage.py migrate --settings=config.settings.production && daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application"