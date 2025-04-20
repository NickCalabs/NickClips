#!/bin/bash
# This script is designed to be run on the Dockge host machine
# It will install yt-dlp in a location that can be mounted by the container

set -e

# Create the directory structure for Dockge/stacks
STACK_NAME="nickclips"  # Change this to match your stack name if different
STACK_PATH="/opt/stacks/$STACK_NAME"
STACK_BIN_PATH="$STACK_PATH/bin"

echo "Creating directories at $STACK_BIN_PATH..."
mkdir -p "$STACK_BIN_PATH"

# Download and install yt-dlp
echo "Downloading yt-dlp to $STACK_BIN_PATH/yt-dlp..."
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o "$STACK_BIN_PATH/yt-dlp" || {
    echo "curl failed, trying wget..."
    wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O "$STACK_BIN_PATH/yt-dlp"
}

# Make yt-dlp executable
echo "Making yt-dlp executable..."
chmod a+rx "$STACK_BIN_PATH/yt-dlp"

# Verify the installation
if [ -x "$STACK_BIN_PATH/yt-dlp" ]; then
    echo "yt-dlp installed successfully at $STACK_BIN_PATH/yt-dlp"
    echo "Testing yt-dlp..."
    "$STACK_BIN_PATH/yt-dlp" --version
    
    echo ""
    echo "==============================================="
    echo "yt-dlp is now ready to be mounted by your container."
    echo "In your docker-compose.yml, make sure to uncomment the mount line:"
    echo "volumes:"
    echo "  - /opt/stacks/$STACK_NAME/bin/yt-dlp:/app/bin/yt-dlp"
    echo "==============================================="
    echo ""
    
    # Create a small test script
    echo "Creating test script..."
    TEST_SCRIPT="$STACK_BIN_PATH/test-ytdlp.sh"
    cat > "$TEST_SCRIPT" << 'EOF'
#!/bin/bash
# Test script for yt-dlp
YTDLP="$(dirname "$0")/yt-dlp"

if [ -x "$YTDLP" ]; then
    echo "Found yt-dlp at: $YTDLP"
    "$YTDLP" --version
    echo "Example usage: $YTDLP -f 'bestvideo[height<=720]+bestaudio/best[height<=720]' --get-url 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'"
else
    echo "Error: yt-dlp not found at $YTDLP"
    exit 1
fi
EOF
    chmod +x "$TEST_SCRIPT"
    
    echo "To test yt-dlp functionality, run: $TEST_SCRIPT"
else
    echo "Error: Failed to install yt-dlp"
    exit 1
fi