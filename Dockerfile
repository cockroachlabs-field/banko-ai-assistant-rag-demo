# Use a multi-stage build for a smaller final image

# Stage 1: Build environment
FROM python:3.9-slim AS builder

WORKDIR /app

# Install system dependencies for sentence-transformers and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime environment
FROM python:3.9-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create config.py from config.example.py if it doesn't exist
RUN if [ ! -f config.py ]; then cp config.example.py config.py; fi

# Expose the Flask port
EXPOSE 5000

# Set environment variables for Flask and AI service
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV AI_SERVICE=watsonx

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/ai-status || exit 1

# Command to run the Flask application
CMD ["flask", "run"]
