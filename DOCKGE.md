# Dockge Deployment Instructions

This file provides instructions for deploying NickClips in Dockge, a container management tool.

## Setup Options

For deploying this application in Dockge, you have three options:

### Option 1: Use compose.yaml (Recommended)

Dockge looks for a file named `compose.yaml` by default. We've created this file with a simplified configuration that should work reliably.

1. Make sure to use the `compose.yaml` file in your stack
2. The Python installer for yt-dlp will be used automatically

### Option 2: Use docker-compose.dockge.yml 

If you prefer to use a separate file:

1. In Dockge, when creating a new stack, select `docker-compose.dockge.yml` as the compose file
2. This file also has a simplified configuration optimized for Dockge

### Option 3: Manual Installation of yt-dlp in Host

If you want to manually install yt-dlp on the host system (for persistent installations):

1. On your host machine (the server running Dockge), run:
   ```bash
   # Create directory for yt-dlp
   mkdir -p /opt/stacks/nickclips/bin
   
   # Download yt-dlp
   curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /opt/stacks/nickclips/bin/yt-dlp
   
   # Make it executable
   chmod a+rx /opt/stacks/nickclips/bin/yt-dlp
   ```

2. Then in your compose file, uncomment the volume mount:
   ```yaml
   volumes:
     - /opt/stacks/nickclips/bin/yt-dlp:/app/bin/yt-dlp
   ```

## Troubleshooting

If you encounter any issues:

1. Check the container logs in Dockge for specific error messages
2. Verify that the Python emergency installer for yt-dlp is running correctly
3. Make sure the container has network access to download yt-dlp
4. Ensure volume mounts are correctly configured

The application is designed to handle yt-dlp installation automatically, but if you're still having issues, consider using the host installation method (Option 3).