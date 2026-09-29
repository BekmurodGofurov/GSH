FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

COPY worker.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "worker.py", "start"]
