# --- Stage 1: build the React frontend ---------------------------------
FROM node:26-alpine AS frontend
WORKDIR /app
RUN npm install -g pnpm@11.5.2
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

# --- Stage 2: install + trim Python deps --------------------------------
# Kept separate from the runtime stage so build-only tools (binutils, used
# to strip debug symbols from compiled extensions) never end up in the
# final image.
FROM python:3.14-slim AS py-builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt ./
RUN pip install --no-cache-dir --no-compile --no-deps -r requirements-prod.txt

# xgboost/pyarrow/scipy/pandas/sklearn/numpy ship compiled extensions with
# debug symbols, plus their own bundled test suites — none of it is needed
# at runtime. Stripping + pruning cuts several hundred MB off the image.
RUN SITE_PACKAGES=/usr/local/lib/python3.14/site-packages && \
    find "$SITE_PACKAGES" -name '*.so' -exec strip --strip-unneeded {} + && \
    find "$SITE_PACKAGES" -regextype posix-extended -regex '.*/tests?$' -type d -exec rm -rf {} + && \
    find "$SITE_PACKAGES" -name '__pycache__' -exec rm -rf {} +

# --- Stage 3: runtime — slim base + trimmed deps + built frontend -------
FROM python:3.14-slim AS backend
WORKDIR /app

COPY --from=py-builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY src/ src/
COPY data/processed/ data/processed/
COPY data/models/ data/models/
COPY --from=frontend /app/dist ./frontend_dist

ENV APP_ENV=production
EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
