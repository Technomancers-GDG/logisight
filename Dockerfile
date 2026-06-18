# Stage 1: Build the admin frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 1b: Build the driver app
FROM node:20-alpine AS driver-builder
WORKDIR /app/driver-app-main
COPY driver-app-main/package*.json ./
RUN npm install
COPY driver-app-main/ .
RUN npm run build

# Stage 2: Build the backend and serve
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (curl added for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Copy the built frontends from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
COPY --from=driver-builder /app/driver-app-main/dist /app/driver-app-main/dist

# Expose port dynamically (Render/Cloud Run pass PORT)
ENV PORT=8000
EXPOSE $PORT

# Healthcheck to ensure app is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Start the application, binding to the dynamic PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
