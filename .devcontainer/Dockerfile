FROM mcr.microsoft.com/devcontainers/python:3.11

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && \
    apt-get install -y nodejs redis-tools postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspaces/auto-broker

# Install Python dependencies
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt || \
    pip install --no-cache-dir fastapi uvicorn sqlalchemy psycopg2-binary redis python-jose python-multipart passlib pydantic-settings python-socketio requests aiohttp beautifulsoup4 asyncpg

# Install global npm packages
RUN npm install -g vite typescript

# Create non-root user (vscode already exists in base image)
USER vscode
