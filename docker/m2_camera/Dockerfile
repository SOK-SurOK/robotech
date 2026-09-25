FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY modules/m2_camera/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY modules/m2_camera/ .

CMD ["python", "main.py"]
