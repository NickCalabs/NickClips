#!/bin/bash

# Exit on error
set -e

# Install directory
YT_DLP_DIR="$HOME/.local/bin"
mkdir -p "$YT_DLP_DIR"

# Download latest yt-dlp
echo "Downloading yt-dlp..."
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o "$YT_DLP_DIR/yt-dlp"
chmod a+rx "$YT_DLP_DIR/yt-dlp"

# Create symbolic link in system path location
mkdir -p $HOME/bin
ln -sf "$YT_DLP_DIR/yt-dlp" "$HOME/bin/yt-dlp"

# Add to PATH if not already there
if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
    echo 'export PATH="$HOME/bin:$PATH"' >> $HOME/.bashrc
    echo 'export PATH="$HOME/bin:$PATH"' >> $HOME/.profile
fi

echo "yt-dlp installed successfully at $YT_DLP_DIR/yt-dlp"
echo "Version information:"
"$YT_DLP_DIR/yt-dlp" --version