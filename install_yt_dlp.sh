#!/bin/bash

# Exit on error
set -e

# Install directory - use a location in the project folder
YT_DLP_DIR="$(pwd)/bin"
mkdir -p "$YT_DLP_DIR"

# Download latest yt-dlp
echo "Downloading yt-dlp..."
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o "$YT_DLP_DIR/yt-dlp"
chmod a+rx "$YT_DLP_DIR/yt-dlp"

# Create a wrapper script to detect system yt-dlp or use the local one
cat > "$YT_DLP_DIR/yt-dlp-wrapper.sh" << 'EOF'
#!/bin/bash

# Try system yt-dlp first
if command -v /nix/store/*/bin/yt-dlp &> /dev/null; then
    exec /nix/store/*/bin/yt-dlp "$@"
elif [ -f "$(dirname "$0")/yt-dlp" ]; then
    # Fall back to local install
    exec "$(dirname "$0")/yt-dlp" "$@"
else
    echo "yt-dlp not found in system path or local directory" >&2
    exit 1
fi
EOF

chmod a+rx "$YT_DLP_DIR/yt-dlp-wrapper.sh"

# Create symbolic links
ln -sf "$YT_DLP_DIR/yt-dlp-wrapper.sh" "$YT_DLP_DIR/yt-dlp-wrapper"

echo "yt-dlp installed successfully at $YT_DLP_DIR/yt-dlp"
echo "Created wrapper script at $YT_DLP_DIR/yt-dlp-wrapper"
echo "Version information:"
"$YT_DLP_DIR/yt-dlp" --version