# Use Python 3.12 slim image for better compatibility and smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for ML models and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    libgthread-2.0-0 \
    libfontconfig1 \
    libgtk-3-0 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies.
# Install CPU-only PyTorch first (from the dedicated CPU wheel index) so we
# don't pull multi-GB CUDA libs on a CPU-only host.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads data scans models logs static

# Set up model caching directory with proper permissions
RUN mkdir -p /root/.cache/huggingface/transformers && \
    chmod 755 /root/.cache/huggingface/transformers

# Ensure Python can find the app module
ENV PYTHONPATH=/app:$PYTHONPATH

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOST=0.0.0.0 \
    PORT=8080 \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers \
    HF_DATASETS_CACHE=/root/.cache/huggingface/datasets

# Expose the port the app runs on
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/healoncal/health || exit 1

# Command to run the application
CMD ["python", "-m", "uvicorn", "app.main_healoncal:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
