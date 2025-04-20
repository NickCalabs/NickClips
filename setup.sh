#!/bin/bash

# Video Share Platform Setup Script
# This script sets up the environment for running the Video Share Platform

# Text formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

echo -e "${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}   Video Share Platform Setup Script    ${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker and Docker Compose before proceeding.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose before proceeding.${NC}"
    exit 1
fi

# Function to generate a random string
generate_random_string() {
    length=$1
    head /dev/urandom | tr -dc A-Za-z0-9 | head -c "$length"
}

# Function to create directories if they don't exist
create_directory() {
    if [ ! -d "$1" ]; then
        echo -e "${YELLOW}Creating directory: $1${NC}"
        mkdir -p "$1"
    fi
}

# Step 1: Create necessary directories
echo -e "${BOLD}Step 1: Creating directories...${NC}"
create_directory "./uploads"
create_directory "./uploads/original"
create_directory "./uploads/processed"
create_directory "./uploads/thumbnails"
create_directory "./uploads/hls"
echo -e "${GREEN}Directories created successfully${NC}"
echo ""

# Step 2: Create .env file from .env.example
echo -e "${BOLD}Step 2: Creating .env file...${NC}"

if [ -f ".env" ]; then
    echo -e "${YELLOW}A .env file already exists. Do you want to overwrite it? (y/n)${NC}"
    read -r overwrite_env
    if [ "$overwrite_env" != "y" ]; then
        echo -e "${BLUE}Keeping existing .env file${NC}"
    else
        cp .env.example .env
        # Generate a secure random string for the SESSION_SECRET
        session_secret=$(generate_random_string 32)
        # Replace the placeholder in the .env file
        sed -i "s/SESSION_SECRET=change_this_to_a_random_secure_string/SESSION_SECRET=$session_secret/" .env
        echo -e "${GREEN}Created new .env file with a randomly generated session secret${NC}"
    fi
else
    cp .env.example .env
    # Generate a secure random string for the SESSION_SECRET
    session_secret=$(generate_random_string 32)
    # Replace the placeholder in the .env file
    sed -i "s/SESSION_SECRET=change_this_to_a_random_secure_string/SESSION_SECRET=$session_secret/" .env
    echo -e "${GREEN}Created .env file with a randomly generated session secret${NC}"
fi
echo ""

# Step 3: Configure domain and upload paths
echo -e "${BOLD}Step 3: Basic configuration...${NC}"
echo -e "${YELLOW}Enter your domain name (default: localhost):${NC}"
read -r domain

if [ -n "$domain" ]; then
    sed -i "s/DOMAIN=yourdomain.com/DOMAIN=$domain/" .env
    sed -i "s/VIRTUAL_HOST=yourdomain.com/VIRTUAL_HOST=$domain/" .env
    sed -i "s/LETSENCRYPT_HOST=yourdomain.com/LETSENCRYPT_HOST=$domain/" .env
    echo -e "${GREEN}Domain set to: $domain${NC}"
else
    echo -e "${BLUE}Using default domain: localhost${NC}"
    sed -i "s/DOMAIN=yourdomain.com/DOMAIN=localhost/" .env
    sed -i "s/VIRTUAL_HOST=yourdomain.com/VIRTUAL_HOST=localhost/" .env
    sed -i "s/LETSENCRYPT_HOST=yourdomain.com/LETSENCRYPT_HOST=localhost/" .env
fi

echo -e "${YELLOW}Enter your email (for Let's Encrypt) (default: none):${NC}"
read -r email

if [ -n "$email" ]; then
    sed -i "s/LETSENCRYPT_EMAIL=your-email@example.com/LETSENCRYPT_EMAIL=$email/" .env
    echo -e "${GREEN}Email set to: $email${NC}"
else
    echo -e "${BLUE}No email provided. Let's Encrypt email remains default.${NC}"
fi

echo -e "${YELLOW}Custom upload path (default: ./uploads):${NC}"
read -r upload_path

if [ -n "$upload_path" ]; then
    sed -i "s|LOCAL_UPLOAD_PATH=./uploads|LOCAL_UPLOAD_PATH=$upload_path|" .env
    create_directory "$upload_path"
    create_directory "$upload_path/original"
    create_directory "$upload_path/processed"
    create_directory "$upload_path/thumbnails"
    create_directory "$upload_path/hls"
    echo -e "${GREEN}Upload path set to: $upload_path${NC}"
else
    echo -e "${BLUE}Using default upload path: ./uploads${NC}"
fi

echo -e "${YELLOW}Custom port (default: 5000):${NC}"
read -r port

if [ -n "$port" ]; then
    sed -i "s/PORT=5000/PORT=$port/" .env
    echo -e "${GREEN}Port set to: $port${NC}"
else
    echo -e "${BLUE}Using default port: 5000${NC}"
fi
echo ""

# Step 4: yt-dlp configuration
echo -e "${BOLD}Step 4: yt-dlp configuration...${NC}"
echo -e "${YELLOW}Do you want to configure a proxy for yt-dlp? (y/n)${NC}"
read -r configure_proxy

if [ "$configure_proxy" = "y" ]; then
    echo -e "${YELLOW}Enter proxy URL (format: http://user:pass@proxy:port):${NC}"
    read -r proxy_url
    sed -i "s|YT_DLP_PROXY=|YT_DLP_PROXY=$proxy_url|" .env
    echo -e "${GREEN}Proxy configured: $proxy_url${NC}"
else
    echo -e "${BLUE}No proxy configured for yt-dlp${NC}"
fi

echo -e "${YELLOW}Do you want to set a download rate limit? (y/n) (default: 500K/s)${NC}"
read -r configure_rate_limit

if [ "$configure_rate_limit" = "y" ]; then
    echo -e "${YELLOW}Enter rate limit (e.g., 1M for 1 MB/s):${NC}"
    read -r rate_limit
    sed -i "s/YT_DLP_RATE_LIMIT=500K/YT_DLP_RATE_LIMIT=$rate_limit/" .env
    echo -e "${GREEN}Rate limit set to: $rate_limit${NC}"
else
    echo -e "${BLUE}Using default rate limit: 500K/s${NC}"
fi

echo -e "${YELLOW}Set maximum video duration in seconds? (default: 3600 = 1 hour)${NC}"
read -r max_duration

if [ -n "$max_duration" ]; then
    sed -i "s/YT_DLP_MAX_DURATION=3600/YT_DLP_MAX_DURATION=$max_duration/" .env
    echo -e "${GREEN}Maximum video duration set to: $max_duration seconds${NC}"
else
    echo -e "${BLUE}Using default maximum duration: 3600 seconds (1 hour)${NC}"
fi
echo ""

# Step 5: Start Docker containers
echo -e "${BOLD}Step 5: Starting Docker containers...${NC}"
echo -e "${YELLOW}Do you want to start the containers now? (y/n)${NC}"
read -r start_containers

if [ "$start_containers" = "y" ]; then
    echo -e "${BLUE}Starting Docker containers...${NC}"
    docker-compose down
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Docker containers started successfully!${NC}"
        echo -e "${BOLD}${BLUE}========================================${NC}"
        echo -e "${BOLD}${GREEN}   Video Share Platform is now running   ${NC}"
        if [ "$domain" = "localhost" ] || [ -z "$domain" ]; then
            echo -e "${BOLD}${GREEN}   Access it at: http://localhost:${port:-5000}   ${NC}"
        else
            echo -e "${BOLD}${GREEN}   Access it at: https://$domain   ${NC}"
        fi
        echo -e "${BOLD}${BLUE}========================================${NC}"
    else
        echo -e "${RED}Failed to start Docker containers. Check the error message above.${NC}"
    fi
else
    echo -e "${BLUE}You can start the containers later with 'docker-compose up -d'${NC}"
    echo -e "${BOLD}${BLUE}========================================${NC}"
    echo -e "${BOLD}${GREEN}   Setup completed successfully!   ${NC}"
    echo -e "${BOLD}${BLUE}========================================${NC}"
fi