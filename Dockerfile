# Dockerfile
FROM python:3.11-slim

# Evita prompts de apt
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias del sistema (Poppler es CLAVE)
RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala deps de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código
COPY app.py .

EXPOSE 8000

# Healthcheck del contenedor → usa nuestro endpoint real
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health'); print('OK')" || exit 1

# Arranque (un proceso, producción)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
