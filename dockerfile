# ==========================================
# STAGE 1: Frontend Builder (Node.js + Vite)
# ==========================================
FROM node:20-slim AS frontend-builder
WORKDIR /app

# Install dependencies first (layer cache)
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm ci

# Copy source and build
COPY frontend/ ./frontend/
RUN cd frontend && npm run build
# vite.config.js writes outDir '../frontend_dist', so the build lands at
# /app/frontend_dist, not /app/frontend/frontend_dist.

# ==========================================
# STAGE 2: Python Wheels Builder
# ==========================================
FROM python:3.13-slim AS py-builder
WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements.txt .

# Build wheels for all sub-dependencies
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# ==========================================
# STAGE 3: Final Runtime
# ==========================================
FROM python:3.13-slim
WORKDIR /app

# Install ONLY runtime dependencies to keep container lightweight
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built wheels and requirements from the py-builder stage
COPY --from=py-builder /app/wheels /wheels
COPY --from=py-builder /app/requirements.txt .

# Install strictly from the local wheels folder, no PyPI access needed
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

# Copy application code
COPY . .

# Copy the compiled React SPA from the frontend-builder stage
COPY --from=frontend-builder /app/frontend_dist ./frontend_dist

# Make the script executable
RUN chmod +x /app/entrypoint.sh

# entrypoint.sh runs migrations first, then starts uvicorn
ENTRYPOINT ["/app/entrypoint.sh"]
