import os
import threading
import logging
import subprocess
import json
import re
import shutil
import time
import requests
from urllib.parse import urlparse, urljoin
from app import db
from models import Video, ProcessingQueue

# Configure yt-dlp path with enhanced debugging
def get_yt_dlp_path():
    """Get the path to yt-dlp executable, trying multiple options with detailed debugging"""
    
    # Print current working directory for debugging
    cwd = os.getcwd()
    logging.info(f"Current working directory: {cwd}")
    
    # Print environment PATH for debugging
    env_path = os.environ.get('PATH', '')
    logging.info(f"Environment PATH: {env_path}")
    
    # Explicitly check if Python can execute commands
    try:
        # Try a simple command to check subprocess functionality
        test_result = subprocess.run(['echo', 'Testing subprocess'], 
                                     capture_output=True, text=True)
        logging.info(f"Subprocess test: {test_result.stdout.strip()}")
    except Exception as e:
        logging.error(f"Subprocess test failed: {str(e)}")
    
    # Common locations to check for yt-dlp - add more Dockge-specific paths
    locations = [
        # Docker container paths
        '/app/bin/yt-dlp',
        '/app/bin/yt-dlp-wrapper',
        '/usr/local/bin/yt-dlp',
        '/usr/local/bin/yt-dlp-wrapper',
        
        # Dockge specific paths
        '/opt/stacks/nickclips/bin/yt-dlp',
        '/opt/stacks/*/bin/yt-dlp',  # Try with wildcard for different stack names
        '/opt/*/bin/yt-dlp',
        
        # Local development paths
        os.path.join(cwd, 'bin', 'yt-dlp'),
        os.path.join(cwd, 'bin', 'yt-dlp-wrapper'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'yt-dlp'),
    ]
    
    # Check each location with detailed logging
    for location in locations:
        # Skip paths with wildcards as os.path cannot handle them directly
        if '*' in location:
            logging.info(f"Skipping wildcard path check (would need glob): {location}")
            continue
            
        logging.info(f"Checking location: {location}")
        if os.path.exists(location):
            logging.info(f"  - File exists at: {location}")
            if os.path.isfile(location):
                logging.info(f"  - It's a file")
                if os.access(location, os.X_OK):
                    logging.info(f"  - And it's executable")
                    return location
                else:
                    logging.warning(f"  - But it's not executable")
            else:
                logging.warning(f"  - But it's not a file (might be a directory)")
        else:
            logging.warning(f"  - File does not exist")
    
    # Try system path via shutil.which with detailed logging
    logging.info("Trying to find yt-dlp in system PATH using shutil.which...")
    system_yt_dlp = shutil.which('yt-dlp')
    if system_yt_dlp:
        logging.info(f"Found yt-dlp in system PATH: {system_yt_dlp}")
        return system_yt_dlp
    else:
        logging.warning("shutil.which could not find yt-dlp in PATH")
    
    # Create a new yt-dlp-wrapper script in the current directory as a last resort
    try:
        logging.info("Attempting to create a new yt-dlp wrapper script as last resort...")
        wrapper_dir = os.path.join(cwd, 'bin')
        os.makedirs(wrapper_dir, exist_ok=True)
        wrapper_path = os.path.join(wrapper_dir, 'yt-dlp-fallback')
        
        with open(wrapper_path, 'w') as f:
            f.write('''#!/bin/bash
# This is an auto-generated fallback script for yt-dlp
# It tries multiple locations where yt-dlp might be installed

# Log our execution for debugging
echo "yt-dlp-fallback wrapper executing, looking for yt-dlp..." >&2

# Try multiple locations
for cmd in "/app/bin/yt-dlp" "/usr/local/bin/yt-dlp" "/opt/stacks/nickclips/bin/yt-dlp" "yt-dlp"; do
    if [ -x "$cmd" ]; then
        echo "Found yt-dlp at $cmd, executing..." >&2
        exec "$cmd" "$@"
    elif command -v "$cmd" >/dev/null 2>&1; then
        echo "Found yt-dlp command: $cmd, executing..." >&2
        exec "$cmd" "$@"
    fi
done

echo "ERROR: yt-dlp not found in any location" >&2
exit 1
''')
        
        os.chmod(wrapper_path, 0o755)  # Make executable
        logging.info(f"Created fallback wrapper at {wrapper_path}")
        return wrapper_path
    except Exception as e:
        logging.error(f"Failed to create fallback wrapper: {str(e)}")
    
    # Log warning about potential issues
    logging.warning("CRITICAL: Could not find yt-dlp at any location. " +
                   "Falling back to 'yt-dlp' command, but this will likely fail.")
    
    # Default to just 'yt-dlp' and hope it's in the PATH
    return 'yt-dlp'

# Get the yt-dlp path once at module load time
logging.info("==== STARTING YT-DLP PATH RESOLUTION ====")
YT_DLP_PATH = get_yt_dlp_path()
logging.info(f"==== RESOLVED YT-DLP PATH: {YT_DLP_PATH} ====")

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def validate_url(url):
    """Validate if a URL is from a supported video platform (strict whitelist only)"""
    import ipaddress
    try:
        result = urlparse(url)

        # Only allow http(s) schemes - blocks file://, ftp://, gopher://, etc.
        if result.scheme not in ('http', 'https'):
            return False

        if not result.netloc:
            return False

        # Block internal/private IP ranges (SSRF protection)
        hostname = result.hostname
        if hostname:
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    logger.warning(f"Blocked internal IP in URL: {hostname}")
                    return False
            except ValueError:
                pass  # Not an IP address, continue with domain check

        # Strict whitelist of supported video platforms
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

        # Strip port from domain if present
        domain = result.hostname.lower() if result.hostname else ''

        # Exact match or proper subdomain match (not substring)
        return any(domain == vd or domain.endswith('.' + vd) for vd in video_domains)

    except Exception:
        return False

def queue_download(video_id, url):
    """Queue a video for download and processing"""
    thread = threading.Thread(target=download_video, args=(video_id, url))
    thread.daemon = True
    thread.start()
    return True

def download_video(video_id, url):
    """Download a video from a URL using yt-dlp with enhanced Twitter and Reddit support"""
    from app import app
    
    with app.app_context():
        video = Video.query.get(video_id)
        if not video:
            logger.error(f"Video {video_id} not found")
            return False
        
        try:
            logger.info(f"Downloading video from URL: {url}")
            
            # Skip if URL is from our own domain
            if 'nickclips.com' in url.lower():
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
            info = None
            
            # Platform-specific info extraction
            if 'reddit.com' in url.lower():
                logger.info("Attempting direct Reddit info extraction first...")
                info = get_reddit_info_directly(url)
                if info:
                    logger.info(f"Successfully got Reddit info directly: {info}")
                else:
                    logger.info("Direct Reddit info extraction failed, falling back to yt-dlp...")
            elif 'twitter.com' in url.lower() or 'x.com' in url.lower():
                logger.info("Attempting direct Twitter info extraction first...")
                info = get_twitter_info_directly(url)
                if info:
                    logger.info(f"Successfully got Twitter info directly: {info}")
                else:
                    logger.info("Direct Twitter info extraction failed, falling back to yt-dlp...")
            
            # If platform-specific extraction failed, try yt-dlp
            if not info:
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
                elif 'reddit.com' in url.lower() or 'twitter.com' in url.lower() or 'x.com' in url.lower():
                    # Try with direct platform-specific download as a last resort before failing
                    logger.info("No info available, directly proceeding with platform-specific download attempt")
                    # Continue with download attempts - don't return False yet
            
            # Platform-specific download attempts
            downloaded_file = None
            
            if 'reddit.com' in url.lower():
                logger.info("Attempting direct Reddit video download first...")
                downloaded_file = try_reddit_direct_download(url, output_template)
                
                if downloaded_file and os.path.exists(downloaded_file):
                    logger.info(f"Direct Reddit download succeeded: {downloaded_file}")
                else:
                    logger.info("Direct Reddit download failed, falling back to yt-dlp...")
            
            elif 'twitter.com' in url.lower() or 'x.com' in url.lower():
                logger.info("Attempting direct Twitter video download first...")
                downloaded_file = try_twitter_direct_download(url, output_template)
                
                if downloaded_file and os.path.exists(downloaded_file):
                    logger.info(f"Direct Twitter download succeeded: {downloaded_file}")
                else:
                    logger.info("Direct Twitter download failed, falling back to yt-dlp...")
            
            # If platform-specific download failed, try yt-dlp
            if not downloaded_file or not os.path.exists(downloaded_file):
                downloaded_file = download_with_ytdlp(url, output_template)
            
            if not downloaded_file or not os.path.exists(downloaded_file):
                # Check for platform-specific error messages
                if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                    error_msg = "YouTube restricts automated downloads on shared hosting. This feature will work on your self-hosted setup."
                elif 'reddit.com' in url.lower():
                    error_msg = "Reddit restricts automated downloads on shared hosting. This feature will work on your self-hosted setup.\n\nNote: YouTube and Reddit downloads are often blocked on cloud platforms. This feature will work properly when self-hosted on your homelab environment."
                elif 'twitter.com' in url.lower() or 'x.com' in url.lower():
                    error_msg = "Twitter/X restricts automated downloads on shared hosting. This feature will work on your self-hosted setup.\n\nNote: Twitter/X downloads are often blocked on cloud platforms. This feature will work properly when self-hosted on your homelab environment."
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
                error_msg = f"Reddit download failed: {str(e)}.\n\nReddit restricts automated downloads on shared hosting. This feature will work on your self-hosted setup.\n\nNote: YouTube and Reddit downloads are often blocked on cloud platforms. This feature will work properly when self-hosted on your homelab environment."
            elif 'twitter.com' in url.lower() or 'x.com' in url.lower():
                error_msg = f"Twitter/X download failed: {str(e)}.\n\nTwitter/X restricts automated downloads on shared hosting. This feature will work on your self-hosted setup.\n\nNote: Twitter/X downloads are often blocked on cloud platforms. This feature will work properly when self-hosted on your homelab environment."
            
            # Update video status
            video.status = 'failed'
            video.error = error_msg
            db.session.commit()
            
            return False

def get_twitter_info_directly(url):
    """Get Twitter/X video information using yt-dlp metadata for accurate titles"""
    logger.info(f"Attempting to get Twitter info via yt-dlp: {url}")
    try:
        from app import app

        yt_dlp_path = get_yt_dlp_path()
        if not yt_dlp_path:
            logger.error("yt-dlp not found for Twitter info extraction")
            return None

        # Normalize URL
        normalized_url = url.replace('x.com/', 'twitter.com/')

        # Use yt-dlp to get metadata without downloading
        cmd = [
            yt_dlp_path,
            "--dump-json",
            "--no-download",
            "--no-playlist",
            "--socket-timeout", "30",
            normalized_url
        ]

        # Add cookies if configured
        if app.config.get("YT_DLP_COOKIES"):
            cookies_path = app.config["YT_DLP_COOKIES"]
            if os.path.exists(cookies_path):
                cmd.insert(-1, "--cookies")
                cmd.insert(-1, cookies_path)

        logger.info(f"Running Twitter info extraction: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            logger.error(f"yt-dlp failed to get Twitter info: {result.stderr[:500]}")
            return None

        if not result.stdout.strip():
            logger.error("No JSON output from yt-dlp for Twitter")
            return None

        data = json.loads(result.stdout)

        # Extract info from yt-dlp output
        # Twitter titles are usually the tweet text (description field)
        title = data.get('description', '') or data.get('title', 'Twitter Video')

        # Truncate long tweets for title (first 100 chars)
        if len(title) > 100:
            title = title[:97] + '...'

        # Get uploader info for description
        uploader = data.get('uploader', '') or data.get('uploader_id', '')
        description = f"Posted by @{uploader}" if uploader else ''

        result_info = {
            'title': title,
            'description': description,
            'thumbnail': data.get('thumbnail'),
            'ext': 'mp4',
            'duration': data.get('duration')
        }

        logger.info(f"Successfully extracted Twitter info via yt-dlp: {result_info}")
        return result_info

    except subprocess.TimeoutExpired:
        logger.error("Twitter info extraction timed out")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Twitter JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting Twitter info: {e}")
        return None

def try_twitter_direct_download(url, output_path):
    """
    Twitter/X downloader using yt-dlp with proper configuration.
    Note: Twitter now requires authentication for many videos. Set YT_DLP_COOKIES
    environment variable to a cookies.txt file exported from your browser.
    """
    logger = logging.getLogger('app.downloader')
    logger.info(f"Twitter direct download starting for: {url}")

    # Normalize URL - convert x.com to twitter.com for better yt-dlp compatibility
    normalized_url = url.replace('x.com/', 'twitter.com/')

    # Create base output filename
    output_base = os.path.splitext(output_path)[0]
    output_file = f"{output_base}.mp4"

    # Import Flask app to get configuration
    from app import app

    try:
        yt_dlp_path = get_yt_dlp_path()
        if not yt_dlp_path:
            logger.error("yt-dlp not found")
            return None

        # Build yt-dlp command with Twitter-optimized settings
        cmd = [
            yt_dlp_path,
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--referer", "https://twitter.com/",
            "--format", "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--geo-bypass",
            "--socket-timeout", "60",
            "--retries", "10",
            "--fragment-retries", "10",
            "-o", output_file,
            "--verbose"
        ]

        # Add cookies if configured - essential for Twitter/X
        if app.config.get("YT_DLP_COOKIES"):
            cookies_path = app.config["YT_DLP_COOKIES"]
            if os.path.exists(cookies_path):
                cmd.extend(["--cookies", cookies_path])
                logger.info(f"Using cookies file: {cookies_path}")
            else:
                logger.warning(f"Cookies file not found: {cookies_path}")

        # Add proxy if configured
        if app.config.get("YT_DLP_PROXY"):
            cmd.extend(["--proxy", app.config["YT_DLP_PROXY"]])

        cmd.append(normalized_url)

        # Run yt-dlp for Twitter
        logger.info(f"Running Twitter download: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Log output for debugging
        if result.stderr:
            logger.debug(f"yt-dlp stderr: {result.stderr}")
        if result.stdout:
            logger.debug(f"yt-dlp stdout: {result.stdout}")

        # Check if file was created and has size
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            logger.info(f"Successfully downloaded Twitter video to: {output_file}")
            return output_file

        # Check for common error patterns
        if "requires authentication" in result.stderr.lower() or "login required" in result.stderr.lower():
            logger.error("Twitter requires authentication. Please set YT_DLP_COOKIES to a cookies.txt file.")
        elif "video unavailable" in result.stderr.lower():
            logger.error("Video is unavailable or has been deleted.")
        else:
            logger.error(f"yt-dlp failed to download Twitter video. stderr: {result.stderr[-500:]}")

        return None

    except subprocess.TimeoutExpired:
        logger.error("Twitter download timed out after 5 minutes")
        return None
    except Exception as e:
        logger.error(f"Error in Twitter download: {str(e)}")
        return None

def get_reddit_info_directly(url):
    """Get Reddit video information using the JSON API for accurate titles"""
    logger.info(f"Attempting to get Reddit info from JSON API: {url}")
    try:
        # Extract post ID from URL
        post_id = None
        if '/comments/' in url:
            parts = url.split('/comments/')
            if len(parts) > 1:
                post_id = parts[1].split('/')[0]

        if not post_id:
            logger.error("Could not extract Reddit post ID from URL")
            return None

        # Use the JSON API for accurate info
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        json_url = f"https://www.reddit.com/comments/{post_id}/.json"
        logger.info(f"Fetching Reddit JSON for info: {json_url}")

        response = requests.get(json_url, headers=headers, timeout=30)

        if response.status_code != 200:
            logger.error(f"Failed to fetch Reddit JSON: {response.status_code}")
            return None

        data = response.json()

        # Navigate the JSON structure to get post info
        try:
            post_data = data[0]['data']['children'][0]['data']

            title = post_data.get('title', 'Reddit Video')
            subreddit = post_data.get('subreddit', '')
            author = post_data.get('author', '')

            # Get thumbnail
            thumbnail = post_data.get('thumbnail', None)
            if thumbnail in ['self', 'default', 'nsfw', 'spoiler', '']:
                thumbnail = None

            # Build description
            description = f"Posted by u/{author} in r/{subreddit}" if author and subreddit else ''

            result = {
                'title': title,
                'description': description,
                'thumbnail': thumbnail,
                'ext': 'mp4',
                'duration': None
            }

            logger.info(f"Successfully extracted Reddit info from JSON: {result}")
            return result

        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error parsing Reddit JSON: {e}")
            return None

    except Exception as e:
        logger.error(f"Error getting Reddit info: {e}")
        return None

def get_video_info(url):
    """Get video information using yt-dlp without downloading with enhanced error handling"""
    try:
        # Skip if URL is from our own domain
        if 'nickclips.com' in url.lower():
            logger.error(f"Cannot get info from own domain: {url}")
            return None
            
        # Import Flask app to get configuration
        from app import app
        
        # Before running command, do a sanity check to make sure yt-dlp exists
        ytdlp_exists = False
        ytdlp_paths_to_try = [
            YT_DLP_PATH,  # First try the module-level resolved path
            '/app/bin/yt-dlp',
            '/usr/local/bin/yt-dlp',
            '/usr/bin/yt-dlp',
            '/opt/stacks/nickclips/bin/yt-dlp',
            os.path.join(os.getcwd(), 'bin', 'yt-dlp'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'yt-dlp'),
            shutil.which('yt-dlp')  # Finally try using PATH
        ]
        
        actual_ytdlp_path = None
        for path in ytdlp_paths_to_try:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                ytdlp_exists = True
                actual_ytdlp_path = path
                logger.info(f"Found usable yt-dlp for info retrieval at: {actual_ytdlp_path}")
                break
        
        if not ytdlp_exists:
            logger.error("yt-dlp executable not found in any location for info retrieval!")
            return None
        
        # Common command arguments for all sites with enhanced headers
        common_args = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            '--add-header', 'Accept-Language: en-US,en;q=0.9',
            '--add-header', 'DNT: 1',
            '--skip-download',
            '--print-json',
            '--geo-bypass',
            '--socket-timeout', '30',
            '--retries', '5',
            '--verbose'  # Add verbose logging
        ]
        
        # Add proxy if configured
        if app.config["YT_DLP_PROXY"]:
            common_args.extend(['--proxy', app.config["YT_DLP_PROXY"]])
            
        # Add rate limit if configured
        if app.config["YT_DLP_RATE_LIMIT"]:
            common_args.extend(['--limit-rate', app.config["YT_DLP_RATE_LIMIT"]])
            
        # Add cookies if configured
        if app.config["YT_DLP_COOKIES"]:
            common_args.extend(['--cookies', app.config["YT_DLP_COOKIES"]])
            
        # Add custom user agent if configured
        if app.config["YT_DLP_USER_AGENT"]:
            # Replace the default user agent
            for i, arg in enumerate(common_args):
                if arg == '--user-agent':
                    common_args[i+1] = app.config["YT_DLP_USER_AGENT"]
                    break
            
        # Add max duration limit if configured
        max_duration = app.config["YT_DLP_MAX_DURATION"]
        if max_duration > 0:
            common_args.extend(['--match-filter', f'duration < {max_duration}'])
        
        if 'reddit.com' in url.lower():
            # Enhanced Reddit-specific info retrieval
            logger.info("Using enhanced Reddit-specific info retrieval")
            cmd = [
                actual_ytdlp_path,
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                '--add-header', 'Accept-Language: en-US,en;q=0.9',
                '--add-header', 'DNT: 1',
                '--skip-download',
                '--print-json',
                '--geo-bypass',
                '--socket-timeout', '30',
                '--retries', '5',
                '--verbose',
                url
            ]
            
            # Add rate limit if configured
            if app.config["YT_DLP_RATE_LIMIT"]:
                cmd.extend(['--limit-rate', app.config["YT_DLP_RATE_LIMIT"]])
                
            # Add max duration limit if configured
            if max_duration > 0:
                cmd.extend(['--match-filter', f'duration < {max_duration}'])
        elif 'twitter.com' in url.lower() or 'x.com' in url.lower():
            # Enhanced Twitter-specific info retrieval
            logger.info("Using enhanced Twitter-specific info retrieval")
            cmd = [
                actual_ytdlp_path,
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                '--add-header', 'Accept-Language: en-US,en;q=0.9',
                '--add-header', 'DNT: 1',
                '--add-header', 'Referer: https://twitter.com/',
                '--skip-download',
                '--print-json',
                '--geo-bypass',
                '--socket-timeout', '30',
                '--retries', '5',
                '--verbose',
                url
            ]
            
            # Add rate limit if configured
            if app.config["YT_DLP_RATE_LIMIT"]:
                cmd.extend(['--limit-rate', app.config["YT_DLP_RATE_LIMIT"]])
                
            # Add max duration limit if configured
            if max_duration > 0:
                cmd.extend(['--match-filter', f'duration < {max_duration}'])
        elif 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
            cmd = [actual_ytdlp_path] + common_args + [
                '--no-playlist',
                url
            ]
        else:
            cmd = [actual_ytdlp_path] + common_args + [url]
        
        # Log the full command for debugging
        logger.info(f"Running video info command: {' '.join(cmd)}")
        
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
        # Safely check if process is defined and has stdout
        process_output = locals().get('process', None)
        if process_output and hasattr(process_output, 'stdout'):
            logger.error(f"Raw output: {process_output.stdout}")
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

def try_reddit_direct_download(url, output_path):
    """
    Reddit video downloader using yt-dlp with proper configuration.
    Handles Reddit's separate video/audio streams automatically.
    """
    logger = logging.getLogger('app.downloader')
    logger.info(f"Reddit direct download starting for: {url}")

    # Create base output filename
    output_base = os.path.splitext(output_path)[0]
    output_file = f"{output_base}.mp4"

    # Import Flask app to get configuration
    from app import app

    try:
        yt_dlp_path = get_yt_dlp_path()
        if not yt_dlp_path:
            logger.error("yt-dlp not found")
            return None

        # Build yt-dlp command with Reddit-optimized settings
        # Reddit videos often have separate audio/video streams that need merging
        cmd = [
            yt_dlp_path,
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--format", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--geo-bypass",
            "--socket-timeout", "60",
            "--retries", "10",
            "--fragment-retries", "10",
            "-o", output_file,
            "--verbose"
        ]

        # Add proxy if configured
        if app.config.get("YT_DLP_PROXY"):
            cmd.extend(["--proxy", app.config["YT_DLP_PROXY"]])

        cmd.append(url)

        # Run yt-dlp for Reddit
        logger.info(f"Running Reddit download: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Log output for debugging
        if result.stderr:
            logger.debug(f"yt-dlp stderr: {result.stderr}")
        if result.stdout:
            logger.debug(f"yt-dlp stdout: {result.stdout}")

        # Check if file was created and has size
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            logger.info(f"Successfully downloaded Reddit video to: {output_file}")
            return output_file

        # If main attempt failed, try the JSON API fallback
        logger.info("yt-dlp failed, trying Reddit JSON API fallback...")
        return try_reddit_json_api_download(url, output_file)

    except subprocess.TimeoutExpired:
        logger.error("Reddit download timed out after 5 minutes")
        return None
    except Exception as e:
        logger.error(f"Error in Reddit download: {str(e)}")
        return None


def try_reddit_json_api_download(url, output_file):
    """
    Fallback Reddit downloader using the JSON API.
    Reddit provides a .json endpoint for posts that contains video URLs.
    """
    logger = logging.getLogger('app.downloader')
    logger.info(f"Trying Reddit JSON API fallback for: {url}")

    try:
        # Extract post ID from URL
        post_id = None
        if '/comments/' in url:
            parts = url.split('/comments/')
            if len(parts) > 1:
                post_id = parts[1].split('/')[0]

        if not post_id:
            logger.error("Could not extract Reddit post ID from URL")
            return None

        # Initialize session with browser-like headers
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        session.headers.update(headers)

        # Try Reddit JSON API
        json_url = f"https://www.reddit.com/comments/{post_id}/.json"
        logger.info(f"Fetching Reddit JSON: {json_url}")

        response = session.get(json_url, timeout=30)
        if response.status_code != 200:
            logger.error(f"Reddit JSON API returned status {response.status_code}")
            return None

        data = response.json()

        # Navigate the JSON structure to find the video URL
        video_url = None
        audio_url = None

        try:
            post_data = data[0]['data']['children'][0]['data']

            # Check for reddit_video in media
            if 'media' in post_data and post_data['media']:
                if 'reddit_video' in post_data['media']:
                    reddit_video = post_data['media']['reddit_video']
                    video_url = reddit_video.get('fallback_url') or reddit_video.get('hls_url')
                    # Audio is usually at a predictable URL
                    if video_url and 'DASH_' in video_url:
                        audio_url = re.sub(r'DASH_\d+\.mp4', 'DASH_audio.mp4', video_url)

            # Check for crosspost_parent_list
            if not video_url and 'crosspost_parent_list' in post_data:
                for crosspost in post_data['crosspost_parent_list']:
                    if 'media' in crosspost and crosspost['media']:
                        if 'reddit_video' in crosspost['media']:
                            reddit_video = crosspost['media']['reddit_video']
                            video_url = reddit_video.get('fallback_url') or reddit_video.get('hls_url')
                            if video_url and 'DASH_' in video_url:
                                audio_url = re.sub(r'DASH_\d+\.mp4', 'DASH_audio.mp4', video_url)
                            break
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error parsing Reddit JSON: {e}")
            return None

        if not video_url:
            logger.error("Could not find video URL in Reddit JSON response")
            return None

        logger.info(f"Found Reddit video URL: {video_url}")

        # Download video
        video_response = session.get(video_url, stream=True, timeout=60)
        if video_response.status_code != 200:
            logger.error(f"Failed to download video: HTTP {video_response.status_code}")
            return None

        temp_video = output_file + ".video.tmp"
        with open(temp_video, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Try to download and merge audio if available
        if audio_url:
            try:
                logger.info(f"Downloading Reddit audio: {audio_url}")
                audio_response = session.get(audio_url, stream=True, timeout=60)
                if audio_response.status_code == 200:
                    temp_audio = output_file + ".audio.tmp"
                    with open(temp_audio, 'wb') as f:
                        for chunk in audio_response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    # Merge video and audio using ffmpeg
                    logger.info("Merging video and audio with ffmpeg...")
                    merge_cmd = [
                        "ffmpeg", "-y",
                        "-i", temp_video,
                        "-i", temp_audio,
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-strict", "experimental",
                        output_file
                    ]
                    merge_result = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=120)

                    # Clean up temp files
                    if os.path.exists(temp_video):
                        os.remove(temp_video)
                    if os.path.exists(temp_audio):
                        os.remove(temp_audio)

                    if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                        logger.info(f"Successfully merged Reddit video with audio: {output_file}")
                        return output_file
            except Exception as e:
                logger.warning(f"Failed to download/merge audio: {e}")

        # If no audio or audio merge failed, just use the video
        if os.path.exists(temp_video):
            os.rename(temp_video, output_file)
            logger.info(f"Downloaded Reddit video (no audio): {output_file}")
            return output_file

        return None

    except Exception as e:
        logger.error(f"Reddit JSON API download failed: {str(e)}")
        return None

def download_with_ytdlp(url, output_template):
    """
    Generic yt-dlp download function as a fallback.
    Platform-specific handlers (try_twitter_direct_download, try_reddit_direct_download)
    are called first by download_video().
    """
    try:
        # Skip if URL is from our own domain
        if 'nickclips.com' in url.lower():
            logger.error(f"Cannot download from own domain: {url}")
            return None

        from app import app

        yt_dlp_path = get_yt_dlp_path()
        if not yt_dlp_path:
            logger.error("yt-dlp not found")
            return None

        # Build command with sensible defaults
        cmd = [
            yt_dlp_path,
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--format", "bestvideo+bestaudio/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--geo-bypass",
            "--socket-timeout", "60",
            "--retries", "10",
            "--fragment-retries", "10",
            "-o", output_template,
            "--verbose"
        ]

        # Add cookies if configured
        if app.config.get("YT_DLP_COOKIES"):
            cookies_path = app.config["YT_DLP_COOKIES"]
            if os.path.exists(cookies_path):
                cmd.extend(["--cookies", cookies_path])

        # Add proxy if configured
        if app.config.get("YT_DLP_PROXY"):
            cmd.extend(["--proxy", app.config["YT_DLP_PROXY"]])

        # Add rate limit if configured
        if app.config.get("YT_DLP_RATE_LIMIT"):
            cmd.extend(["--limit-rate", app.config["YT_DLP_RATE_LIMIT"]])

        # Add max duration limit if configured
        max_duration = app.config.get("YT_DLP_MAX_DURATION", 0)
        if max_duration > 0:
            cmd.extend(["--match-filter", f"duration < {max_duration}"])

        cmd.append(url)

        logger.info(f"Running yt-dlp: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.stdout:
            logger.debug(f"yt-dlp stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"yt-dlp stderr: {result.stderr}")

        # Find the downloaded file
        slug = os.path.basename(output_template).split('.')[0]
        dir_path = os.path.dirname(output_template)

        for filename in os.listdir(dir_path):
            if filename.startswith(slug + '.'):
                filepath = os.path.join(dir_path, filename)
                if os.path.getsize(filepath) > 1000:
                    return filepath

        return None

    except subprocess.TimeoutExpired:
        logger.error("yt-dlp download timed out after 5 minutes")
        return None
    except Exception as e:
        logger.error(f"Error downloading with yt-dlp: {e}")
        return None
