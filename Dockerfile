FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt
COPY . .
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --log-file - --access-logfile -"]
