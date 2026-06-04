web: daphne -b 0.0.0.0 -p $PORT config.asgi:application
worker: celery -A config.celery worker --loglevel=info --pool=solo
beat: celery -A config.celery beat --loglevel=info