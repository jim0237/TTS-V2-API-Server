# Use NVIDIA CUDA base image
FROM nvidia/cuda:12.6.3-base-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    PIP_NO_CACHE_DIR=1

# Install dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    espeak-ng \
    libsndfile1 \
    curl \
    openssl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && find /var/cache -type f -delete

# Set up application directory
WORKDIR /app

# Create and activate virtual environment
RUN python -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies in virtual environment with error checking
RUN . /app/venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt || { echo "Pip install failed"; exit 1; } && \
    echo "Verifying installed packages:" && \
    pip list | tee /tmp/pip-list.txt && \
    if ! grep -q "torch" /tmp/pip-list.txt; then \
        echo "torch package not found in installed packages!"; \
        exit 1; \
    fi && \
    rm /tmp/pip-list.txt && \
    find /usr/local -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true

# Copy application files
COPY main-ui.py main.py entrypoint.sh ./
COPY templates templates/

# Set up directories and SSL cert in one layer
RUN chmod +x entrypoint.sh && \
    mkdir -p voices && \
    openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout /app/key.pem -out /app/cert.pem -days 365 \
        -subj '/CN=localhost'

# Create non-root user and set permissions
RUN useradd -m -u 1000 tts && \
    chown -R tts:tts /app && \
    chmod 600 key.pem && \
    chmod 644 cert.pem

USER tts

# Configure container
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -k -f https://localhost:8000/ || exit 1

# Set command to use entrypoint script
CMD ["/bin/bash", "/app/entrypoint.sh"]
