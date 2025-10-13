FROM python:3.14.0-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY setup.py .
COPY ocode_python/ ./ocode_python/
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m -u 1000 ocode && \
    chown -R ocode:ocode /app

# Switch to non-root user
USER ocode

# Set up environment
ENV PYTHONPATH=/app
ENV OCODE_MODEL=llama3:8b
ENV OLLAMA_HOST=http://ollama:11434

# Create volume mount point for workspace
VOLUME ["/workspace"]

# Set default working directory to workspace
WORKDIR /workspace

# Entry point
ENTRYPOINT ["ocode"]
CMD ["--help"]
