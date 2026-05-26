FROM python:3.11-slim

# Evita que o Python grave arquivos .pyc em disco (foco em Retenção Zero)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# O Gunicorn é o servidor web de produção recomendado pelo Google Cloud
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app