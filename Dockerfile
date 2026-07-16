FROM python:3.12-slim

WORKDIR /app

# Install production Python dependencies
COPY requirements-prod.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-prod.txt

# Install Chromium and its required Linux dependencies
RUN playwright install --with-deps chromium

# Copy backend source code
COPY backend ./backend

# Copy only the production quantized ONNX model
COPY nlp/exports/quantized_model ./nlp/exports/quantized_model

# Backend imports use "from app..."
WORKDIR /app/backend

# Python runtime configuration
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Render provides PORT automatically.
# 10000 is the fallback for local Docker execution.
ENV PORT=10000

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]