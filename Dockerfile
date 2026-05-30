FROM python:3.11-slim

# Instala as ferramentas nativas de OCR e manipulação de PDF do Linux
RUN apt-get update && apt-get install -y \
    ocrmypdf \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 app:app