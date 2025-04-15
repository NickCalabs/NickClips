# Installation Guide

This guide helps you install and run VideoShare platform on your server.

## Prerequisites

- A Linux server (Ubuntu, Debian, etc.)
- Docker and Docker Compose installed
- At least 2GB of RAM for optimal performance

## Step-by-Step Installation

### 1. Install Docker and Docker Compose (if not already installed)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/video-share-platform.git
cd video-share-platform
```

### 3. Configure the Application

Update the docker-compose.yml file to set a secure session secret:

```bash
# Generate a random string
SECRET=$(openssl rand -hex 32)

# Replace the default session secret
sed -i "s/change_this_to_a_random_secure_string/$SECRET/" docker-compose.yml
```

### 4. Start the Application

```bash
# Start in detached mode
docker-compose up -d
```

### 5. Access Your Application

The application will be running at `http://your-server-ip:5000`

The first user to register will automatically become an admin.

### 6. Upgrading

To upgrade to a newer version:

```bash
# Pull latest changes
git pull

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

### Reset Database

If you need to reset the database:

```bash
docker-compose down
docker volume rm video-share-platform_postgres_data
docker-compose up -d
```

## Proxying with Nginx (Optional)

For production use, it's recommended to put Nginx in front of the application:

```
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Increase upload size limit if needed
    client_max_body_size 1024M;
}
```

Don't forget to add SSL with Let's Encrypt for production use!