FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRG32_KIT_DATA=/data \
    PRG32_KIT_PORT=5090

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data && useradd -ms /bin/bash kit && chown -R kit:kit /data /app
USER kit

EXPOSE 5090
CMD ["python", "app.py"]
