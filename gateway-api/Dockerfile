FROM python:3.11-slim

WORKDIR /app

COPY gateway-api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared_schemas/ /app/shared_schemas/
COPY gateway-api/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]