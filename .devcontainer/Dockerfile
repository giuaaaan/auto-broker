FROM mcr.microsoft.com/devcontainers/python:3.11

# Install system dependencies (for ChromaDB, sentence-transformers, etc.)
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libpq-dev \
    redis-tools \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspaces/auto-broker

# Install Python dependencies in multiple steps for better caching
# Step 1: Core dependencies
RUN pip install --no-cache-dir \
    fastapi uvicorn sqlalchemy asyncpg psycopg2-binary \
    python-jose python-multipart passlib pydantic-settings

# Step 2: Caching & Queue
RUN pip install --no-cache-dir redis

# Step 3: HTTP Clients
RUN pip install --no-cache-dir httpx>=0.27.0 requests aiohttp

# Step 4: Vector DB & AI (these can be heavy)
RUN pip install --no-cache-dir chromadb>=0.5.0 sentence-transformers>=2.2.0

# Step 5: Utilities
RUN pip install --no-cache-dir python-dotenv python-dateutil pytz tenacity

# Step 6: Monitoring & Logging
RUN pip install --no-cache-dir structlog prometheus-client

# Install global npm packages
RUN npm install -g vite typescript

# Switch to non-root user
USER vscode
