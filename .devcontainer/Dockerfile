FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

# Install Node.js
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt || pip install fastapi uvicorn sqlalchemy psycopg2-binary redis python-jose[cryptography] python-multipart passlib[bcrypt] pydantic-settings python-socketio requests aiohttp beautifulsoup4

# Install global npm packages
RUN npm install -g npm@latest
