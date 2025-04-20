#!/bin/bash
# This script should be run inside the Docker container to install yt-dlp
# Usage: docker exec -it <container_name> bash -c "./docker-install-ytdlp.sh"

set -e

echo "Installing yt-dlp directly in Docker container..."

# Make sure we have the directory 
mkdir -p /app/bin

# Download the latest yt-dlp
echo "Downloading yt-dlp..."
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /app/bin/yt-dlp
chmod a+rx /app/bin/yt-dlp

# Verify the installation
echo "yt-dlp installed at /app/bin/yt-dlp"
if [ -x "/app/bin/yt-dlp" ]; then
    echo "Checking version:"
    /app/bin/yt-dlp --version
    
    # Create symlinks to other common locations
    echo "Creating symlinks to common locations..."
    
    # /usr/local/bin is a standard location
    if [ -d "/usr/local/bin" ]; then
        ln -sf /app/bin/yt-dlp /usr/local/bin/yt-dlp
        echo "Created symlink at /usr/local/bin/yt-dlp"
    fi
    
    # /usr/bin is another standard location
    if [ -d "/usr/bin" ]; then
        ln -sf /app/bin/yt-dlp /usr/bin/yt-dlp
        echo "Created symlink at /usr/bin/yt-dlp"
    fi
    
    echo "Installation successful!"
else
    echo "ERROR: Failed to install yt-dlp - executable not found or not executable"
    exit 1
fi

# Print current PATH
echo "Current PATH: $PATH"