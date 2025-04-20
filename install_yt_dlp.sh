#!/bin/bash

# Exit on error
set -e

# Determine installation directory - try to support multiple environments
if [ -d "/app" ]; then
    # Docker environment
    YT_DLP_DIR="/app/bin"
elif [ -d "/opt/stacks/nickclips" ]; then
    # Dockge environment
    YT_DLP_DIR="/opt/stacks/nickclips/bin"
else
    # Local development
    YT_DLP_DIR="$(pwd)/bin"
fi

# Create the directory
mkdir -p "$YT_DLP_DIR"
echo "Installing yt-dlp to $YT_DLP_DIR"

# Download latest yt-dlp
echo "Downloading yt-dlp..."
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o "$YT_DLP_DIR/yt-dlp"
chmod a+rx "$YT_DLP_DIR/yt-dlp"

# Create a wrapper script to detect yt-dlp in multiple locations
cat > "$YT_DLP_DIR/yt-dlp-wrapper" << 'EOF'
#!/bin/bash

# Try common locations for yt-dlp installation
if [ -x "/app/bin/yt-dlp" ]; then
    exec "/app/bin/yt-dlp" "$@"
elif [ -x "/usr/local/bin/yt-dlp" ]; then
    exec "/usr/local/bin/yt-dlp" "$@"
elif [ -x "/opt/stacks/nickclips/bin/yt-dlp" ]; then
    exec "/opt/stacks/nickclips/bin/yt-dlp" "$@"
elif [ -x "$(dirname "$0")/yt-dlp" ]; then
    # Same directory as wrapper
    exec "$(dirname "$0")/yt-dlp" "$@"
elif command -v yt-dlp &> /dev/null; then
    # Found in PATH
    exec yt-dlp "$@"
else
    echo "Error: yt-dlp not found in any standard location" >&2
    exit 1
fi
EOF

chmod a+rx "$YT_DLP_DIR/yt-dlp-wrapper"

# Also create a symlink in /usr/local/bin if we have permission
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    ln -sf "$YT_DLP_DIR/yt-dlp" "/usr/local/bin/yt-dlp"
    ln -sf "$YT_DLP_DIR/yt-dlp-wrapper" "/usr/local/bin/yt-dlp-wrapper"
    echo "Created symlinks in /usr/local/bin/"
fi

echo "yt-dlp installed successfully at $YT_DLP_DIR/yt-dlp"
echo "Created wrapper script at $YT_DLP_DIR/yt-dlp-wrapper"
echo "Version information:"
"$YT_DLP_DIR/yt-dlp" --version