FROM python:3.12-slim

# Install Node.js for Pi
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Pi globally
RUN npm install -g @mariozechner/pi-coding-agent

# Python deps
RUN pip install --no-cache-dir fastapi uvicorn python-docx

# Create app dir
WORKDIR /app

# Mount point for travel skills (read-only)
RUN mkdir -p /app/travel

EXPOSE 8091

CMD ["python3", "/app/web/app.py"]
