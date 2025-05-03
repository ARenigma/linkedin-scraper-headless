#!/bin/bash

# Install playwright browsers
echo "Installing Playwright browsers..."
python -m playwright install chromium

# Create output directory
mkdir -p output

echo "Setup completed successfully!" 