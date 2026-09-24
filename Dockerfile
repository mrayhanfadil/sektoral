# syntax=docker/dockerfile:1

# 1. Build the React app. The fonts and brand SVGs it imports live in app/assets.
FROM node:22-slim AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
COPY app/assets /src/app/assets
RUN npm run build

# 2. Python runtime. The Playwright image ships Chromium for PDF rendering.
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HOME=/tmp \
    SECTORAL_HOST=0.0.0.0 \
    SECTORAL_PORT=8765 \
    SECTORAL_OUT=/app/out/web \
    SECTORAL_REPORTS=/app/out/reports
# poppler-utils renders report cover thumbnails (pdftoppm).
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv --system-site-packages /opt/venv
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY agents ./agents
COPY scripts ./scripts
COPY spec ./spec
COPY data ./data
COPY --from=web /src/web/dist ./web/dist
RUN mkdir -p out && chmod -R a+rwX data out
USER pwuser
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/tickers', timeout=4)"
CMD ["python", "-m", "app.server"]
