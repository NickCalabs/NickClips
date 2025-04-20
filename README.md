# Video Share Platform

A lightweight self-hosted video sharing platform similar to Streamable with link downloading and direct uploads. Designed for easy deployment with Docker on any home server, NAS, or cloud environment.

## Features

- Upload videos directly from your device
- Download videos from popular platforms (YouTube, Twitter, etc.) via URLs
- Automatic video processing with FFmpeg
- HLS adaptive streaming for optimized playback
- User authentication system with admin capabilities
- Simple and responsive UI with light/dark mode support
- Mobile-friendly video player
- Thumbnails are automatically generated
- Easy deployment options with Nginx Proxy Manager, Cloudflare Tunnel, or Traefik
- Support for external storage (NAS/NFS) through Docker volume mounts

## Prerequisites

- Docker and Docker Compose
- FFmpeg (included in the Docker image)
- yt-dlp (included in the Docker image, or can use host installation)
- A reverse proxy for HTTPS support (optional, but recommended)

## About yt-dlp in Docker

This application uses yt-dlp for downloading videos from URLs. The Docker setup includes multiple paths to find yt-dlp:

1. **Built-in yt-dlp**: The Docker image includes yt-dlp installed at `/app/bin/yt-dlp`.
2. **Host system yt-dlp**: You can mount your host system's yt-dlp binary into the container (useful for Dockge or custom stacks).
3. **Fallback mechanism**: The application will search multiple common locations for yt-dlp.

For Dockge users, you can uncomment the relevant volume mount in docker-compose.yml:

```yaml
volumes:
  - ${LOCAL_UPLOAD_PATH:-./uploads}:${UPLOAD_FOLDER:-/app/uploads}
  # If using Dockge/stacks, uncomment this:
  #- /opt/stacks/nickclips/bin/yt-dlp:/app/bin/yt-dlp
```

You can use the included `install_yt_dlp.sh` script to download and install yt-dlp in multiple locations if needed.

## Quick Start

1. Clone this repository:
```bash
git clone https://github.com/yourusername/video-share-platform.git
cd video-share-platform
```

2. Run the setup script to configure your environment:
```bash
./setup.sh
```
This script will generate a secure SESSION_SECRET, create necessary directories, and ask for basic configuration.

3. Alternatively, you can manually configure:
```bash
# Create a .env file from the example
cp .env.example .env
# Edit the .env file with your settings
nano .env
# Start the application
docker-compose up -d
```

4. Access the app at http://localhost:5000 (or your configured domain)

5. The first user to register will automatically be granted admin privileges!

## Configuration Options

You can customize the application by changing variables in your `.env` file:

### Database
- `DATABASE_URL`: PostgreSQL connection string
- `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`, `PGDATABASE`: Individual PostgreSQL connection parameters

### Security
- `SESSION_SECRET`: Secret key for session management (important for security)

### Storage
- `UPLOAD_FOLDER`: Directory path inside the container for video storage
- `LOCAL_UPLOAD_PATH`: Path on your host machine to mount to the container
- `MAX_CONTENT_LENGTH`: Maximum file upload size in bytes (default 1GB)

### Video Processing
- `MAX_VIDEOS_PER_USER`: Limit the number of videos per user (default 50)
- `CONCURRENT_PROCESSING`: Number of videos to process concurrently (default 1)

### yt-dlp Settings
- `YT_DLP_PROXY`: HTTP proxy for video downloads (format: http://user:pass@proxy:port)
- `YT_DLP_RATE_LIMIT`: Download speed limit (e.g., "500K" for 500 KB/s)
- `YT_DLP_MAX_DURATION`: Maximum video duration in seconds (default 3600 = 1 hour)

## Storage Management

Videos are stored in the mounted volumes:
- `/uploads/original`: Original uploaded files
- `/uploads/processed`: Transcoded videos
- `/uploads/thumbnails`: Generated thumbnails
- `/uploads/hls`: HLS streaming files

You can customize the storage location by setting `LOCAL_UPLOAD_PATH` in your `.env` file.

## Deployment Options

### Using Nginx Proxy Manager

1. Make sure Nginx Proxy Manager is running on your server
2. In your `.env` file, set:
   ```
   PORT=5000
   VIRTUAL_HOST=videos.yourdomain.com
   ```
3. In Nginx Proxy Manager:
   - Add a new proxy host
   - Set the domain to `videos.yourdomain.com`
   - Set the scheme to `http`
   - Set the forward hostname/IP to the IP of your Docker host
   - Set the forward port to `5000`
   - Enable SSL with Let's Encrypt

### Using Cloudflare Tunnel

1. Create a Cloudflare Tunnel in your Cloudflare Zero Trust dashboard
2. Configure a public hostname pointing to your service
3. Install cloudflared on your server
4. Run your tunnel with:
   ```bash
   cloudflared tunnel run --url http://localhost:5000 your-tunnel-id
   ```
5. Alternatively, add a service in `docker-compose.yml`:
   ```yaml
   cloudflared:
     image: cloudflare/cloudflared
     restart: unless-stopped
     command: tunnel run --token YOUR_TUNNEL_TOKEN
     networks:
       - videoshare-network
   ```

### Using Traefik (Built into docker-compose.yml)

1. Make sure you have Traefik running as your reverse proxy
2. In your `.env` file, set:
   ```
   DOMAIN=videos.yourdomain.com
   ```
3. The labels in the docker-compose.yml file already include the necessary Traefik configuration

## Accessing from Mobile Devices/Other Networks

If you want to access your Video Share instance from outside your home network:

1. Set up a proper domain name pointing to your server
2. Configure your router to forward the appropriate port to your server
3. Use a service like Cloudflare Tunnel for secure access without port forwarding

## Limitations

- When running on resource-constrained servers, processing large videos might be slow
- YouTube and some platforms may block the download in some cases due to their policies
- For videos larger than 1GB, adjust the `MAX_CONTENT_LENGTH` setting in the `.env` file

## Troubleshooting

- **"Cannot connect to the Docker daemon"**: Make sure Docker is running on your system
- **Database connection errors**: Check the PostgreSQL container is running and credentials are correct
- **"Permission denied" errors**: Check the permissions on your upload directories
- **Video download failures**: Some platforms restrict automated downloads. Consider using a proxy

### Fixing "No such file or directory: 'yt-dlp'" Error

If you're getting an error like `[Errno 2] No such file or directory: 'yt-dlp'` in your Docker deployment, there are several solutions:

1. **Use the built-in installation script**:
   ```bash
   # Execute inside the container
   docker exec -it your-container-name bash -c "chmod +x /app/docker-install-ytdlp.sh && /app/docker-install-ytdlp.sh"
   ```

2. **Install yt-dlp manually inside the container**:
   ```bash
   docker exec -it your-container-name bash -c "mkdir -p /app/bin && curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /app/bin/yt-dlp && chmod a+rx /app/bin/yt-dlp"
   ```

3. **For Dockge users**:
   - Install yt-dlp on the host:
     ```bash
     mkdir -p /opt/stacks/nickclips/bin
     curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /opt/stacks/nickclips/bin/yt-dlp
     chmod a+rx /opt/stacks/nickclips/bin/yt-dlp
     ```
   - Uncomment the mount in docker-compose.yml:
     ```yaml
     volumes:
       - /opt/stacks/nickclips/bin/yt-dlp:/app/bin/yt-dlp
     ```

4. **Check your PATH**:
   Make sure the application can find yt-dlp. The PATH environment variable in the docker-compose.yml is already set to include `/app/bin`.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT