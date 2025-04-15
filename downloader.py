import os
import threading
import logging
import subprocess
import json
import re
from urllib.parse import urlparse
from app import db
from models import Video, ProcessingQueue

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def validate_url(url):
    """Validate if a URL is supported by yt-dlp"""
    # Basic URL validation
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False
        
        # Check if the URL is from a supported site
        # This is a simple check for common video sites
        video_domains = [
            'youtube.com', 'youtu.be',
            'vimeo.com',
            'dailymotion.com',
            'twitter.com', 'x.com',
            'facebook.com', 'fb.com',
            'instagram.com',
            'tiktok.com',
            'twitch.tv',
            'reddit.com'
        ]
        
        domain = result.netloc.lower()
        if any(video_domain in domain for video_domain in video_domains):
            return True
        
        # For other URLs, we could do a more thorough check with yt-dlp
        # but that would be slower, so for simplicity we'll just allow them
        return True
        
    except Exception:
        return False

def queue_download(video_id, url):
    """Queue a video for download and processing"""
    thread = threading.Thread(target=download_video, args=(video_id, url))
    thread.daemon = True
    thread.start()
    return True

def download_video(video_id, url):
    """Download a video from a URL using yt-dlp"""
    from app import app
    
    with app.app_context():
        video = Video.query.get(video_id)
        if not video:
            logger.error(f"Video {video_id} not found")
            return False
        
        try:
            logger.info(f"Downloading video from URL: {url}")
            
            # Skip if URL is from our own domain
            if 'replit.dev' in url.lower() or 'repl.co' in url.lower():
                error_msg = "Cannot download videos from our own domain"
                logger.error(error_msg)
                video.status = 'failed'
                video.error = error_msg
                db.session.commit()
                return False
            
            # Create the output directory
            output_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'original')
            os.makedirs(output_dir, exist_ok=True)
            
            # Set output filename template
            output_template = os.path.join(output_dir, f"{video.slug}.%(ext)s")
            
            # Get video info first to set title and description
            info = get_video_info(url)
            
            if info:
                video.title = info.get('title', 'Untitled')
                video.description = info.get('description', '')
                db.session.commit()
            else:
                if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                    error_msg = "YouTube downloads are restricted on this platform. This will likely work on your local setup."
                    video.status = 'failed'
                    video.error = error_msg
                    db.session.commit()
                    logger.error(error_msg)
                    return False
                elif 'reddit.com' in url.lower():
                    error_msg = "Reddit downloads are restricted on this platform. This will likely work on your local setup."
                    video.status = 'failed'
                    video.error = error_msg
                    db.session.commit()
                    logger.error(error_msg)
                    return False
            
            # Download the video
            downloaded_file = download_with_ytdlp(url, output_template)
            
            if not downloaded_file or not os.path.exists(downloaded_file):
                # Check for platform-specific error messages
                if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                    error_msg = "YouTube restricts automated downloads on shared hosting. This feature will work on your self-hosted setup."
                elif 'reddit.com' in url.lower():
                    error_msg = "Reddit restricts automated downloads on shared hosting. This feature will work on your self-hosted setup."
                else:
                    error_msg = "Failed to download video. This will likely work in your self-hosted environment."
                
                video.status = 'failed'
                video.error = error_msg
                db.session.commit()
                logger.error(error_msg)
                return False
            
            # Update the video record
            video.original_path = downloaded_file
            video.status = 'pending'
            db.session.commit()
            
            # Add to processing queue
            queue_item = ProcessingQueue(video_id=video.id, priority=1)
            db.session.add(queue_item)
            db.session.commit()
            
            # Start processing
            from video_processor import process_next
            process_next()
            
            return True
            
        except Exception as e:
            logger.exception(f"Error downloading video from {url}: {e}")
            
            # Generate a more helpful error message
            error_msg = str(e)
            if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                error_msg = f"YouTube download failed on Replit: {str(e)}. This will work in your self-hosted environment."
            elif 'reddit.com' in url.lower():
                error_msg = f"Reddit download failed on Replit: {str(e)}. This will work in your self-hosted environment."
            
            # Update video status
            video.status = 'failed'
            video.error = error_msg
            db.session.commit()
            
            return False

def get_video_info(url):
    """Get video information using yt-dlp without downloading"""
    try:
        # Skip if URL is from our own domain
        if 'replit.dev' in url.lower() or 'repl.co' in url.lower():
            logger.error(f"Cannot get info from own domain: {url}")
            return None
            
        # Common command arguments for all sites
        common_args = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--skip-download',
            '--print-json',
            '--no-check-certificate',
            '--geo-bypass'
        ]
        
        if 'reddit.com' in url.lower():
            cmd = ['yt-dlp'] + common_args + ['--verbose', url]
        elif 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
            cmd = ['yt-dlp'] + common_args + [
                '--no-playlist',
                url
            ]
        else:
            cmd = ['yt-dlp'] + common_args + [url]
        
        # Run the command and capture output
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        # Log the output for debugging
        if process.stderr:
            logger.debug(f"yt-dlp stderr: {process.stderr}")
        
        # Check return code and parse output
        process.check_returncode()
        
        if not process.stdout.strip():
            raise Exception("No JSON data returned from yt-dlp")
        
        info = json.loads(process.stdout)
        
        # Extract useful information
        result = {
            'title': info.get('title', 'Untitled'),
            'description': info.get('description', ''),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail'),
            'ext': info.get('ext', 'mp4')
        }
        
        # Add more debug logging
        logger.debug(f"Got video info: {result}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        # Safely check if process is defined
        if 'process' in locals():
            logger.error(f"Raw output: {process.stdout}")
        else:
            logger.error("No process output available")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp process error: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            logger.error(f"yt-dlp stderr: {e.stderr}")
        if hasattr(e, 'stdout') and e.stdout:
            logger.error(f"yt-dlp stdout: {e.stdout}")
        return None
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None

def download_with_ytdlp(url, output_template):
    """Download a video using yt-dlp"""
    try:
        # Skip if URL is from our own domain
        if 'replit.dev' in url.lower() or 'repl.co' in url.lower():
            logger.error(f"Cannot download from own domain: {url}")
            return None
            
        # Common command arguments
        common_args = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--format', 'best[ext=mp4]/best',  # Simplify format selection to avoid errors
            '--merge-output-format', 'mp4',
            '--output', output_template,
            '--no-check-certificate',  # Skip HTTPS certificate validation
            '--geo-bypass',  # Try to bypass geo-restrictions
            '--no-playlist',  # Don't download playlists
            '--extract-audio',  # Also extract audio
            '--audio-format', 'mp3',  # Save audio as mp3
            '--audio-quality', '0',  # Best audio quality
            '--verbose'  # Show detailed logs
        ]
        
        # Add site-specific optimizations
        if 'reddit.com' in url.lower():
            cmd = ['yt-dlp'] + common_args + [url]
        elif 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
            # YouTube specific arguments
            cmd = ['yt-dlp'] + common_args + [
                '--concurrent-fragments', '5',  # Use 5 fragments at a time
                url
            ]
        else:
            cmd = ['yt-dlp'] + common_args + [url]
        
        # Run the command and capture output
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        # Log the output for debugging
        if process.stdout:
            logger.debug(f"yt-dlp stdout: {process.stdout}")
        if process.stderr:
            logger.debug(f"yt-dlp stderr: {process.stderr}")
        
        # Check if the process was successful
        process.check_returncode()
        
        # Determine the actual filename
        slug = os.path.basename(output_template).split('.')[0]
        dir_path = os.path.dirname(output_template)
        
        # Look for files with the slug
        for filename in os.listdir(dir_path):
            if filename.startswith(slug + '.'):
                return os.path.join(dir_path, filename)
        
        return None
        
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp process error: {e}")
        if e.stderr:
            logger.error(f"yt-dlp stderr: {e.stderr}")
        if e.stdout:
            logger.error(f"yt-dlp stdout: {e.stdout}")
        return None
    except Exception as e:
        logger.error(f"Error downloading with yt-dlp: {e}")
        return None
