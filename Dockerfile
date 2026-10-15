FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRG32_KIT_DATA=/data \
    PRG32_KIT_PORT=5090

WORKDIR /app

COPY requirements.txt requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt

COPY . .
RUN mkdir -p /data && useradd -ms /bin/bash kit && chown -R kit:kit /data /app
USER kit

EXPOSE 5090
# Several workers and threads serve many students at once. Long builds wait for a
# build slot (PRG32_MAX_PARALLEL_BUILDS), so the request timeout is generous.
CMD ["sh", "-c", "exec gunicorn --preload --workers ${PRG32_KIT_WORKERS:-2} --threads ${PRG32_KIT_THREADS:-16} --timeout 600 --bind 0.0.0.0:${PRG32_KIT_PORT:-5090} app:app"]
