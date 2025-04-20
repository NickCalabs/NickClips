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
