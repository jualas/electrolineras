# syntax=docker/dockerfile:1

FROM node:22-alpine AS web-build
WORKDIR /build
COPY src/web/package.json src/web/package-lock.json ./
RUN npm ci
COPY src/web .
# Mismo origen: API sirve estáticos; sin prefijo /api externo
ENV VITE_API_URL=
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

COPY --from=web-build /build/dist ./src/web/dist

# Sin root: uid 1000 coincide con el dueño del volumen de datos en el host
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data && chown 1000:1000 /app/data
USER 1000:1000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
