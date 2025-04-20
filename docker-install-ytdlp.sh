#!/bin/bash
# This script should be run inside the Docker container to install yt-dlp
# Usage: docker exec -it <container_name> bash -c "./docker-install-ytdlp.sh"

set -e

echo "Installing yt-dlp directly in Docker container..."

# Make sure we have the directory 
mkdir -p /app/bin

# Install curl if it's missing - check for both Debian/Ubuntu and Alpine
if ! command -v curl &> /dev/null; then
    echo "curl not found, installing..."
    
    # Check if we're in Alpine Linux
    if [ -f /etc/alpine-release ]; then
        echo "Detected Alpine Linux, using apk..."
        apk update && apk add --no-cache curl
    elif [ -f /etc/debian_version ]; then
        echo "Detected Debian/Ubuntu, using apt-get..."
        apt-get update && apt-get install -y curl
    elif command -v yum &> /dev/null; then
        echo "Detected RHEL/CentOS, using yum..."
        yum install -y curl
    elif command -v dnf &> /dev/null; then
        echo "Detected Fedora, using dnf..."
        dnf install -y curl
    else
        echo "Unknown distribution, trying apt-get as fallback..."
        apt-get update && apt-get install -y curl || {
            echo "apt-get failed, trying apk..."
            apk update && apk add --no-cache curl || {
                echo "ERROR: Could not install curl with any known package manager"
            }
        }
    fi
fi

# Download the latest yt-dlp
echo "Downloading yt-dlp..."
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /app/bin/yt-dlp || {
    echo "curl failed, trying wget..."
    if ! command -v wget &> /dev/null; then
        echo "wget not found, installing..."
        # Check for distribution type like we did for curl
        if [ -f /etc/alpine-release ]; then
            echo "Detected Alpine Linux, using apk..."
            apk update && apk add --no-cache wget
        elif [ -f /etc/debian_version ]; then
            echo "Detected Debian/Ubuntu, using apt-get..."
            apt-get update && apt-get install -y wget
        elif command -v yum &> /dev/null; then
            echo "Detected RHEL/CentOS, using yum..."
            yum install -y wget
        elif command -v dnf &> /dev/null; then
            echo "Detected Fedora, using dnf..."
            dnf install -y wget
        else
            echo "Unknown distribution, trying apt-get as fallback..."
            apt-get update && apt-get install -y wget || {
                echo "apt-get failed, trying apk..."
                apk update && apk add --no-cache wget || {
                    echo "ERROR: Could not install wget with any known package manager"
                }
            }
        fi
    fi
    wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /app/bin/yt-dlp
}
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