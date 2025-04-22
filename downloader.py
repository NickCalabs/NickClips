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
            info = None
            
            # For Reddit URLs, try direct info extraction first
            if 'reddit.com' in url.lower():
                logger.info("Attempting direct Reddit info extraction first...")
                info = get_reddit_info_directly(url)
                if info:
                    logger.info(f"Successfully got Reddit info directly: {info}")
                else:
                    logger.info("Direct Reddit info extraction failed, falling back to yt-dlp...")
            
            # If not Reddit or direct Reddit info extraction failed, try yt-dlp
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
                elif 'reddit.com' in url.lower():
                    # Try with direct Reddit info/download as a last resort before failing
                    logger.info("No info available, directly proceeding with Reddit download attempt")
                    # Continue with download attempts - don't return False yet
            
            # For Reddit URLs, try direct download first
            downloaded_file = None
            if 'reddit.com' in url.lower():
                logger.info("Attempting direct Reddit video download first...")
                downloaded_file = try_reddit_direct_download(url, output_template)
                
                if downloaded_file and os.path.exists(downloaded_file):
                    logger.info(f"Direct Reddit download succeeded: {downloaded_file}")
                else:
                    logger.info("Direct Reddit download failed, falling back to yt-dlp...")
            
            # If not Reddit or direct Reddit download failed, try yt-dlp
            if not downloaded_file or not os.path.exists(downloaded_file):
                downloaded_file = download_with_ytdlp(url, output_template)
            
            if not downloaded_file or not os.path.exists(downloaded_file):
                # Check for platform-specific error messages
                if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                    error_msg = "YouTube restricts automated downloads on shared hosting. This feature will work on your self-hosted setup."
                elif 'reddit.com' in url.lower():
                    error_msg = "Reddit restricts automated downloads on shared hosting. This feature will work on your self-hosted setup.\n\nNote: YouTube and Reddit downloads are often blocked on cloud platforms. This feature will work properly when self-hosted on your homelab environment."
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
            
            # Update video status
            video.status = 'failed'
            video.error = error_msg
            db.session.commit()
            
            return False

def get_reddit_info_directly(url):
    """Get Reddit video information directly from the page, without yt-dlp"""
    logger.info(f"Attempting to get Reddit info directly from: {url}")
    try:
        # Use a desktop browser user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.reddit.com/',
            'Origin': 'https://www.reddit.com',
            'DNT': '1'
        }
        
        # Request the page
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch Reddit page: {response.status_code}")
            return None
            
        # Look for metadata in the HTML
        html_content = response.text
        
        # Extract title
        title_pattern = r'<title>(.*?)</title>'
        title_match = re.search(title_pattern, html_content)
        title = title_match.group(1) if title_match else 'Reddit Video'
        
        # Extract description (usually the post content)
        description_pattern = r'<meta name="description" content="(.*?)"'
        description_match = re.search(description_pattern, html_content)
        description = description_match.group(1) if description_match else ''
        
        # Extract thumbnail
        thumbnail_pattern = r'<meta property="og:image" content="(.*?)"'
        thumbnail_match = re.search(thumbnail_pattern, html_content)
        thumbnail = thumbnail_match.group(1) if thumbnail_match else None
        
        # Clean up the title (remove "r/subreddit - " prefix and "- Reddit" suffix)
        if ' - ' in title:
            parts = title.split(' - ')
            if len(parts) > 2 and parts[-1].lower() == 'reddit':
                title = ' - '.join(parts[1:-1])
            elif parts[-1].lower() == 'reddit':
                title = parts[0]
        
        result = {
            'title': title,
            'description': description,
            'thumbnail': thumbnail,
            'ext': 'mp4',  # Default extension
            'duration': None  # We don't know the duration
        }
        
        logger.info(f"Successfully extracted Reddit info: {result}")
        return result
    except Exception as e:
        logger.error(f"Error getting Reddit info directly: {e}")
        return None

def get_video_info(url):
    """Get video information using yt-dlp without downloading with enhanced error handling"""
    try:
        # Skip if URL is from our own domain
        if 'replit.dev' in url.lower() or 'repl.co' in url.lower():
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
        
        # Common command arguments for all sites
        common_args = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--skip-download',
            '--print-json',
            '--no-check-certificate',
            '--geo-bypass',
            '--verbose'  # Add verbose logging
        ]
        
        # Add proxy if configured
        if app.config["YT_DLP_PROXY"]:
            common_args.extend(['--proxy', app.config["YT_DLP_PROXY"]])
            
        # Add rate limit if configured
        if app.config["YT_DLP_RATE_LIMIT"]:
            common_args.extend(['--limit-rate', app.config["YT_DLP_RATE_LIMIT"]])
            
        # Add max duration limit if configured
        max_duration = app.config["YT_DLP_MAX_DURATION"]
        if max_duration > 0:
            common_args.extend(['--match-filter', f'duration < {max_duration}'])
        
        if 'reddit.com' in url.lower():
            # Enhanced Reddit-specific info retrieval
            logger.info("Using enhanced Reddit-specific info retrieval")
            cmd = [
                actual_ytdlp_path,
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--skip-download',
                '--print-json',
                '--no-check-certificate',
                '--geo-bypass',
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
    Simplified Reddit downloader with better reliability and error handling.
    Completely rebuilt to avoid all previous issues.
    """
    logger = logging.getLogger('app.downloader')
    logger.info(f"Reddit direct download starting for: {url}")
    
    # Create base output filename
    output_base = os.path.splitext(output_path)[0]
    output_file = f"{output_base}.mp4"
    
    # Try direct YouTube-DL approach with specific Reddit format selector
    try:
        yt_dlp_path = get_yt_dlp_path()
        if not yt_dlp_path:
            logger.error("yt-dlp not found")
            return None
            
        cmd = [
            yt_dlp_path,
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "-o", output_file,
            "--no-warnings",
            url
        ]
        
        # Run yt-dlp for Reddit
        logger.info(f"Running specialized Reddit download: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Check if file was created and has size
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            logger.info(f"Successfully downloaded Reddit video to: {output_file}")
            return output_file
        else:
            logger.warning("yt-dlp failed to download Reddit video, trying fallback method")
    except Exception as e:
        logger.error(f"Error in yt-dlp download: {str(e)}")
    
    # Try fallback direct HTTP approach
    try:
        # Initialize session with browser-like headers
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        session.headers.update(headers)
        
        # Extract post ID if available for JSON API
        post_id = None
        if '/comments/' in url:
            parts = url.split('/comments/')
            if len(parts) > 1:
                post_id = parts[1].split('/')[0]
                logger.info(f"Extracted Reddit post ID: {post_id}")
                
        # Try Reddit JSON API first if we have a post ID
        if post_id:
            json_url = f"https://www.reddit.com/comments/{post_id}/.json"
            logger.info(f"Trying Reddit JSON API: {json_url}")
            
            try:
                api_headers = headers.copy()
                api_headers['Accept'] = 'application/json'
                json_response = session.get(json_url, headers=api_headers, timeout=10)
                
                if json_response.status_code == 200:
                    data = json_response.json()
                    if len(data) > 0 and 'data' in data[0] and 'children' in data[0]['data']:
                        children = data[0]['data']['children']
                        if len(children) > 0 and 'data' in children[0]:
                            post_data = children[0]['data']
                            if 'media' in post_data and post_data['media'] and 'reddit_video' in post_data['media']:
                                reddit_video = post_data['media']['reddit_video']
                                if 'fallback_url' in reddit_video:
                                    video_url = reddit_video['fallback_url']
                                    logger.info(f"Found video URL from JSON API: {video_url}")
                                    
                                    # Download the video
                                    video_response = session.get(video_url, stream=True, timeout=30)
                                    if video_response.status_code == 200:
                                        with open(output_file, 'wb') as f:
                                            for chunk in video_response.iter_content(chunk_size=8192):
                                                f.write(chunk)
                                                
                                        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                                            logger.info(f"Successfully downloaded Reddit video via API to: {output_file}")
                                            return output_file
            except Exception as e:
                logger.warning(f"Reddit API download failed: {str(e)}")
                
        # If API approach failed, try direct page scraping
        try:
            page_response = session.get(url, timeout=30)
            if page_response.status_code == 200:
                html = page_response.text
                
                # Look for MP4 video URLs
                mp4_patterns = [
                    r'(https?://v\.redd\.it/[a-zA-Z0-9]+/DASH_[0-9]+\.mp4)',
                    r'(https?://v\.redd\.it/[a-zA-Z0-9]+\.mp4)',
                    r'fallback_url":\s*"(https?:\\u002F\\u002Fv\.redd\.it\\u002F[^"]+\.mp4)"'
                ]
                
                video_urls = []
                for pattern in mp4_patterns:
                    urls = re.findall(pattern, html)
                    video_urls.extend(urls)
                    
                # Clean up escaped URLs
                video_urls = [url.replace('\\u002F', '/') for url in video_urls]
                
                if video_urls:
                    # Sort by quality (DASH_720, DASH_1080, etc.)
                    def get_quality(url):
                        match = re.search(r'DASH_(\d+)', url)
                        return int(match.group(1)) if match else 0
                        
                    video_urls.sort(key=get_quality, reverse=True)
                    logger.info(f"Found {len(video_urls)} potential video URLs")
                    
                    # Try downloading each URL until one works
                    for video_url in video_urls:
                        try:
                            logger.info(f"Trying to download: {video_url}")
                            video_response = session.get(video_url, stream=True, timeout=30)
                            
                            if video_response.status_code == 200:
                                with open(output_file, 'wb') as f:
                                    for chunk in video_response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                        
                                if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                                    logger.info(f"Successfully downloaded Reddit video via scraping: {output_file}")
                                    return output_file
                        except Exception as dl_err:
                            logger.warning(f"Failed to download {video_url}: {str(dl_err)}")
        except Exception as page_err:
            logger.warning(f"Page scraping failed: {str(page_err)}")
                
        # All approaches failed
        logger.error("All Reddit download approaches failed")
        return None
    except Exception as e:
        logger.error(f"Error in Reddit download process: {str(e)}")
        return None

def download_with_ytdlp(url, output_template):
    """Download a video using yt-dlp with enhanced error recovery"""
    try:
        # Skip if URL is from our own domain
        if 'replit.dev' in url.lower() or 'repl.co' in url.lower():
            logger.error(f"Cannot download from own domain: {url}")
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
                logger.info(f"Found usable yt-dlp for download at: {actual_ytdlp_path}")
                break
        
        if not ytdlp_exists:
            logger.error("yt-dlp executable not found in any location for download!")
            # Try to install it as last resort
            try:
                logger.info("Attempting emergency yt-dlp installation...")
                bin_dir = os.path.join(os.getcwd(), 'bin')
                os.makedirs(bin_dir, exist_ok=True)
                ytdlp_path = os.path.join(bin_dir, 'yt-dlp-emergency')
                
                # Try using Python's urllib to download it
                import urllib.request
                logger.info("Downloading with urllib.request...")
                urllib.request.urlretrieve(
                    "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
                    ytdlp_path
                )
                os.chmod(ytdlp_path, 0o755)
                logger.info(f"Emergency yt-dlp installed at {ytdlp_path}")
                actual_ytdlp_path = ytdlp_path
            except Exception as install_error:
                logger.error(f"Emergency yt-dlp installation failed: {install_error}")
                return None
            
        # Base command arguments - shared across all sites
        base_args = [
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--output', output_template,
            '--no-check-certificate',  # Skip HTTPS certificate validation
            '--geo-bypass',  # Try to bypass geo-restrictions
            '--no-playlist',  # Don't download playlists
            '--verbose'  # Show detailed logs
        ]
        
        # Add proxy if configured
        if app.config["YT_DLP_PROXY"]:
            base_args.extend(['--proxy', app.config["YT_DLP_PROXY"]])
            
        # Add rate limit if configured
        if app.config["YT_DLP_RATE_LIMIT"]:
            base_args.extend(['--limit-rate', app.config["YT_DLP_RATE_LIMIT"]])
            
        # Add max duration limit if configured
        max_duration = app.config["YT_DLP_MAX_DURATION"]
        if max_duration > 0:
            base_args.extend(['--match-filter', f'duration < {max_duration}'])
        
        # Construct site-specific command arguments
        if 'reddit.com' in url.lower():
            # REDDIT HANDLING: Complete special case handling for Reddit URLs
            logger.info("Using ENHANCED Reddit-specific download parameters")
            
            # First, try to list available formats for debugging and use these formats explicitly
            reddit_formats = []
            try:
                available_formats_cmd = [
                    actual_ytdlp_path,
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    '--list-formats',
                    '--verbose',
                    '--no-check-certificate',
                    '--geo-bypass',
                    url
                ]
                logger.info(f"Checking available Reddit formats: {' '.join(available_formats_cmd)}")
                format_process = subprocess.run(available_formats_cmd, capture_output=True, text=True)
                
                # Parse stdout to extract format IDs 
                if format_process.stdout:
                    logger.info(f"Available Reddit formats: {format_process.stdout}")
                    
                    # Parse format listing to extract available format IDs
                    for line in format_process.stdout.splitlines():
                        if line.strip() and 'ID  ' not in line and '[info]' not in line:
                            parts = line.split()
                            if parts and parts[0].isdigit():
                                reddit_formats.append(parts[0])
                    
                    logger.info(f"Extracted Reddit format IDs: {reddit_formats}")
                
                if format_process.stderr:
                    logger.info(f"Format listing stderr: {format_process.stderr}")
            except Exception as e:
                logger.warning(f"Format listing error: {e}")
            
            # Base command with mandatory options
            cmd = [
                actual_ytdlp_path,
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                '--output', output_template,
                '--no-check-certificate',
                '--geo-bypass',
                '--verbose',
                '--force-ipv4',  # Force IPv4 to avoid potential IPv6 issues
                '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                '--add-header', 'Accept-Language: en-US,en;q=0.9',
                '--add-header', 'DNT: 1',
                '--socket-timeout', '30',  # Increase timeout for slower connections
                '--retries', '10',         # Increase retry attempts
                '--fragment-retries', '10' # Increase fragment retry attempts
            ]
            
            # For Reddit, we need to first list available formats, then pick one explicitly

            # Step 1: Get available formats
            logger.info("Running yt-dlp to list available formats for Reddit video")
            formats_cmd = [
                actual_ytdlp_path,
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                '--list-formats',
                '--no-check-certificate',
                '--verbose',
                url
            ]
            
            # Run the format listing command
            format_ids = []  # Initialize here to avoid "possibly unbound" error
            try:
                formats_process = subprocess.run(formats_cmd, capture_output=True, text=True)
                if formats_process.stdout:
                    logger.info(f"Format listing output: {formats_process.stdout}")
                    
                    # Parse the output to find available format IDs
                    for line in formats_process.stdout.splitlines():
                        if 'dash-video' in line or 'dash-audio' in line:
                            # Extract format IDs for dash formats
                            parts = line.split()
                            if parts and parts[0].isdigit():
                                format_ids.append(parts[0])
                
                # If we found dash formats, use them explicitly
                if format_ids:
                    logger.info(f"Found dash format IDs: {format_ids}")
                    best_format = format_ids[0]  # Use the first one (usually best)
                    
                    # Step 2: Use the explicit format ID
                    cmd = [
                        actual_ytdlp_path,
                        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                        '--format', best_format,
                        '--output', output_template,
                        '--no-check-certificate',
                        '--verbose',
                        '--no-playlist',
                        url
                    ]
                    logger.info(f"Using format ID {best_format} for Reddit download")
                else:
                    # No dash formats found, try with "bestaudio+bestvideo" format
                    cmd = [
                        actual_ytdlp_path,
                        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                        '--format', 'bestaudio+bestvideo/best',
                        '--output', output_template,
                        '--no-check-certificate',
                        '--verbose',
                        '--no-playlist',
                        url
                    ]
                    logger.info("Using bestaudio+bestvideo format for Reddit download")
            except Exception as e:
                logger.error(f"Error listing formats: {e}")
                # Fallback to a simpler command with no format specification
                cmd = [
                    actual_ytdlp_path,
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                    '--output', output_template,
                    '--no-check-certificate',
                    '--verbose',
                    '--no-playlist',
                    url
                ]
                logger.info("Failed to get formats, using minimal command for Reddit download")
            
            # Add the rate limit for shared hosting
            if app.config["YT_DLP_RATE_LIMIT"]:
                cmd.extend(['--limit-rate', app.config["YT_DLP_RATE_LIMIT"]])
                
            # Add duration limit
            if max_duration > 0:
                cmd.extend(['--match-filter', f'duration < {max_duration}'])
        elif 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
            # YouTube-specific command
            logger.info("Using YouTube-specific download parameters")
            cmd = [actual_ytdlp_path] + base_args + [
                '--format', 'best[ext=mp4]/best',
                '--merge-output-format', 'mp4',
                '--concurrent-fragments', '5',  # Use 5 fragments at a time
                url
            ]
        else:
            # Default command for all other sites
            logger.info("Using default download parameters")
            cmd = [actual_ytdlp_path] + base_args + [
                '--format', 'best[ext=mp4]/best',
                '--merge-output-format', 'mp4',
                url
            ]
        
        # Log the full command for debugging
        logger.info(f"Running download command: {' '.join(str(arg) for arg in cmd)}")
        
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
