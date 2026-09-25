FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY modules/m1_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY modules/m1_api/ .

CMD ["python", "main.py"]
