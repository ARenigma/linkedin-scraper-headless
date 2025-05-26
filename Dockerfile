FROM python:alpine

# Install system dependencies for Chromium
RUN apk add --no-cache \
    wget gnupg curl ca-certificates \
    ttf-liberation libappindicator alsa-lib \
    at-spi2-atk cups dbus \
    gdk-pixbuf nss libx11-dev \
    libxcomposite libxdamage libxrandr xdg-utils \
    vulkan-loader

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/usr/local/share/.cache/ms-playwright

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright and Chromium
RUN pip install playwright && playwright install chromium

# Copy project files
COPY . /app
WORKDIR /app

# Command to run your scraper
CMD ["python", "main.py"]
