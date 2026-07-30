# Netmera Multi-Agent Yardım Masası — production image.
# chroma_db/ ve data/ imaja gomulur (statik referans veri); calisma-zamani
# verisi (storage/*.db) docker-compose.yml'de kalici bir volume olarak
# ayrilir — bkz. DEPLOY.md.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# storage/ kalici volume olarak mount edilecek (bkz. docker-compose.yml)
VOLUME ["/app/storage"]

EXPOSE 8501 8502
