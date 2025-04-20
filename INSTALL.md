# Installation Guide

This guide helps you install and run VideoShare platform on your server.

## Prerequisites

- A Linux server (Ubuntu, Debian, etc.) or Docker-capable system (Windows with Docker Desktop, macOS, NAS systems)
- Docker and Docker Compose installed
- At least 2GB of RAM for optimal performance
- 10GB+ disk space for video storage (recommended)

## Installation Options

### Option 1: Using the Setup Script (Recommended)

This is the easiest way to get started:

```bash
# Clone the repository
git clone https://github.com/yourusername/video-share-platform.git
cd video-share-platform

# Make the setup script executable and run it
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Generate a secure session secret
- Create necessary directories
- Ask for your domain name and other configuration options
- Start the Docker containers

### Option 2: Manual Installation

If you prefer to set up manually:

#### 1. Install Docker and Docker Compose (if not already installed)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/video-share-platform.git
cd video-share-platform
```

#### 3. Configure the Environment

```bash
# Copy the example environment file
cp .env.example .env

# Generate a random secret
SECRET=$(openssl rand -hex 32)

# Update the session secret in the .env file
sed -i "s/SESSION_SECRET=change_this_to_a_random_secure_string/SESSION_SECRET=$SECRET/" .env

# Edit other settings as needed
nano .env
```

#### 4. Create Required Directories

```bash
mkdir -p uploads/original uploads/processed uploads/thumbnails uploads/hls
```

#### 5. Start the Application

```bash
docker-compose up -d
```

## Platform-Specific Instructions

### Docker on Synology NAS

1. Install Docker from the Synology Package Center
2. Use SSH to connect to your NAS
3. Follow the manual installation steps above
4. For storage, set `LOCAL_UPLOAD_PATH` in your `.env` file to a shared folder like `/volume1/videos`

### TrueNAS Scale

1. Create a new dataset for storage (e.g., `videos`)
2. Deploy using Docker or Apps
3. Mount your dataset to `/app/uploads` in the container
4. Set `LOCAL_UPLOAD_PATH` to your dataset path

### LXC (Proxmox)

1. Create a new LXC container with Ubuntu or Debian
2. Install Docker and Docker Compose in the container
3. Follow the manual installation steps
4. If using ZFS storage, consider mounting a ZFS dataset to `/app/uploads`

## Environment Variables

Important configuration options in `.env`:

### Database
```
DATABASE_URL=postgresql://postgres:postgres@db:5432/videoshare
PGUSER=postgres
PGPASSWORD=postgres
PGHOST=db
PGPORT=5432
PGDATABASE=videoshare
```

### Storage
```
UPLOAD_FOLDER=/app/uploads
LOCAL_UPLOAD_PATH=./uploads  # Host path to mount into container
MAX_CONTENT_LENGTH=1073741824  # 1GB max file size
```

### yt-dlp Configuration
```
YT_DLP_PROXY=  # Optional HTTP proxy
YT_DLP_RATE_LIMIT=500K  # Download speed limit
YT_DLP_MAX_DURATION=3600  # Max video length in seconds
```

## Accessing Your Installation

The application will be running at:
- `http://localhost:5000` (local access)
- `http://your-server-ip:5000` (network access)
- `https://your-domain.com` (if configured with a proxy)

The first user to register will automatically become an admin.

## Upgrading

To upgrade to a newer version:

```bash
# Pull latest changes
git pull

# Update environment if needed
cp -n .env.example .env.example.new
diff .env.example.new .env.example  # Check for new options

# Rebuild and restart containers
docker-compose down
docker-compose up --build -d
```

## Troubleshooting

### Logs

View application logs:

```bash
docker-compose logs -f web
```

View database logs:

```bash
docker-compose logs -f db
```

### Common Issues

#### Video Processing Fails
- Check if the container has enough memory (`docker stats`)
- Increase Docker memory limits if needed
- Check disk space (`df -h`)

#### Cannot Connect to Database
- Verify PostgreSQL container is running (`docker-compose ps`)
- Check database credentials in `.env`

#### Permission Denied Errors
- Check permissions on upload directories:
  ```bash
  sudo chown -R 1000:1000 uploads/
  sudo chmod -R 755 uploads/
  ```

#### Video Downloads Failing
- Some platforms restrict automated downloads
- Try configuring a proxy in `.env` (YT_DLP_PROXY)
- Check network connectivity from the container

### Reset Database

If you need to reset the database:

```bash
docker-compose down
docker volume rm video-share-platform_postgres_data
docker-compose up -d
```

## Proxy Configuration

### Nginx Proxy Manager

1. In Nginx Proxy Manager:
   - Add a new Proxy Host
   - Set domain name
   - Forward hostname/IP to Docker host IP
   - Forward port to 5000
   - Enable SSL/TLS with Let's Encrypt

### Standard Nginx

```nginx
server {
    listen 80;
    server_name videos.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name videos.yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Recommended SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    
    # Proxy to Docker container
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (needed for some features)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Increase upload size limit for videos
    client_max_body_size 1024M;
}
```

### Cloudflare Tunnel

1. Log in to Cloudflare Zero Trust dashboard
2. Navigate to Access > Tunnels
3. Create a new tunnel and install the connector
4. Add a public hostname:
   - Domain: videos.yourdomain.com
   - Service: HTTP
   - URL: localhost:5000

### Traefik (Already configured in docker-compose.yml)

1. Ensure Traefik is running as your reverse proxy
2. Set `DOMAIN=videos.yourdomain.com` in your `.env` file
3. The Docker labels in docker-compose.yml will handle the rest