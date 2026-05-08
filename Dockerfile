# Blackreach — Multi-stage build for minimal production image
FROM python:3.13-slim

WORKDIR /app

# Install Playwright system deps + runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates procps \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/* && apt-get autoclean

# Copy and install the wheel
COPY dist/blackreach-5.0.0b1-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/blackreach-5.0.0b1-py3-none-any.whl[all]

# Install Playwright and Chromium browser
RUN python -m playwright install chromium --with-deps

# Copy prompts (bundled in wheel but ensure they're accessible)
COPY prompts/ /app/prompts/

# Create data directory
RUN mkdir -p /data/.blackreach && chmod -R 755 /data

ENV BLACKREACH_DATA_DIR=/data/.blackreach
ENV BLACKREACH_LOG_DIR=/data/.blackreach/logs

# Default to interactive mode if no command given
ENTRYPOINT ["blackreach"]
CMD ["--help"]
