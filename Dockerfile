FROM python:3.10-slim

ENV PIP_NO_CACHE_DIR 1

# Installing only required system packages
RUN apt update && apt upgrade -y && \
    apt install --no-install-recommends -y \
    bash \
    git \
    curl \
    wget \
    sqlite3 \
    libsqlite3-dev \
    libffi-dev \
    libjpeg-dev \
    libwebp-dev \
    zlib1g \
    ffmpeg \
    libopus0 \
    libopus-dev \
    && rm -rf /var/lib/apt/lists /var/cache/apt/archives /tmp

# Upgrade pip and setuptools
RUN pip3 install --upgrade pip setuptools

# Set working directory inside container
WORKDIR /app

# Copy requirements first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy all project files to container
COPY . .

# Run the bot
CMD ["python3", "-m", "shivu"]
