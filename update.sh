#!/bin/bash
# NickClips Update Script
# Run this after pushing changes to GitHub

set -e
cd /opt/stacks/nickclips

echo "Pulling latest from GitHub..."
git pull origin master

echo "Restarting web container..."
docker compose restart web

echo "Done! Check logs with: docker logs -f nickclips-web-1"
