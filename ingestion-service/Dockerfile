FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY ingestion-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY shared_schemas/ /app/shared_schemas/
COPY ingestion-service/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]