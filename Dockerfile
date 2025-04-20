FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3-dev \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp in multiple locations for compatibility
RUN mkdir -p /usr/local/bin /app/bin && \
    curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /app/bin/yt-dlp && \
    chmod a+rx /app/bin/yt-dlp && \
    ln -sf /app/bin/yt-dlp /usr/local/bin/yt-dlp

# Create a wrapper script for yt-dlp that tries multiple locations
RUN echo '#!/bin/bash\n\
if [ -x "/app/bin/yt-dlp" ]; then\n\
    exec /app/bin/yt-dlp "$@"\n\
elif [ -x "/usr/local/bin/yt-dlp" ]; then\n\
    exec /usr/local/bin/yt-dlp "$@"\n\
elif [ -x "/opt/stacks/nickclips/bin/yt-dlp" ]; then\n\
    exec /opt/stacks/nickclips/bin/yt-dlp "$@"\n\
else\n\
    echo "Error: yt-dlp not found in standard locations" >&2\n\
    exit 1\n\
fi' > /app/bin/yt-dlp-wrapper && \
    chmod a+rx /app/bin/yt-dlp-wrapper && \
    ln -sf /app/bin/yt-dlp-wrapper /usr/local/bin/yt-dlp-wrapper

# Add bin directory to PATH
ENV PATH="/app/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads/original uploads/processed uploads/thumbnails uploads/hls && \
    chmod -R 755 uploads

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=main.py

# Expose port
EXPOSE 5000

# Create startup script
RUN echo '#!/bin/bash\npython migrations.py\ngunicorn --bind 0.0.0.0:5000 --workers 4 main:app' > /app/start.sh && \
    chmod +x /app/start.sh

# Run the application with migrations
CMD ["/app/start.sh"]