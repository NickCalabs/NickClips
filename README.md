# Video Share Platform

A lightweight self-hosted video sharing platform similar to Streamable with link downloading and direct uploads.

## Features

- Upload videos directly from your device
- Download videos from popular platforms (YouTube, Twitter, etc.) via URLs
- Automatic video processing with FFmpeg
- HLS adaptive streaming for optimized playback
- User authentication system with admin capabilities
- Simple and responsive UI
- Mobile-friendly video player
- Thumbnails are automatically generated

## Prerequisites

- Docker and Docker Compose

## Quick Start

1. Clone this repository:
```bash
git clone https://github.com/yourusername/video-share-platform.git
cd video-share-platform
```

2. Configure your environment:
   - Edit the `docker-compose.yml` file if needed
   - Make sure to change the `SESSION_SECRET` to a secure random string

3. Start the application:
```bash
docker-compose up -d
```

4. Access the app at http://localhost:5000

5. The first user to register will automatically be granted admin privileges!

## Configuration Options

You can customize the application by changing these environment variables in docker-compose.yml:

- `DATABASE_URL`: PostgreSQL connection string
- `SESSION_SECRET`: Secret key for session management (important for security)
- `UPLOAD_FOLDER`: Directory to store uploaded videos and processed files

## Storage Management

Videos are stored in the mounted volumes:
- `/uploads/original`: Original uploaded files
- `/uploads/processed`: Transcoded videos
- `/uploads/thumbnails`: Generated thumbnails
- `/uploads/hls`: HLS streaming files

## Limitations

- When running on resource-constrained servers, processing large videos might be slow
- YouTube and some platforms may block the download in some cases due to their policies

## License

MIT