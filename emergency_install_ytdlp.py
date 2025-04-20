#!/usr/bin/env python3
"""
Emergency yt-dlp installer script that uses only Python's built-in modules
to download the yt-dlp binary without relying on curl or wget.

Usage: python emergency_install_ytdlp.py

This will download yt-dlp to a 'bin' directory in the current directory
and make it executable.
"""

import os
import sys
import urllib.request
import ssl
import logging
import stat

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='[emergency_install] %(levelname)s: %(message)s')

def main():
    """Main installation function"""
    # URL to the latest yt-dlp release
    YT_DLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
    
    # Create bin directory (prioritize /app/bin for Docker compatibility)
    if os.path.isdir('/app'):
        bin_dir = '/app/bin'
        os.makedirs(bin_dir, exist_ok=True)
        logging.info(f"Using Docker standard directory: {bin_dir}")
    else:
        bin_dir = os.path.join(os.getcwd(), 'bin')
        os.makedirs(bin_dir, exist_ok=True)
        logging.info(f"Created local directory: {bin_dir}")
    
    # Path to save yt-dlp
    ytdlp_path = os.path.join(bin_dir, 'yt-dlp')
    
    # If file exists but is a symlink, remove it to prevent circular references
    if os.path.islink(ytdlp_path):
        try:
            real_path = os.path.realpath(ytdlp_path)
            if real_path == ytdlp_path:
                logging.warning(f"Removing circular symlink: {ytdlp_path} -> itself")
                os.remove(ytdlp_path)
            elif real_path.endswith('yt-dlp') and '/bin/yt-dlp' in real_path:
                logging.warning(f"Removing potentially problematic symlink: {ytdlp_path} -> {real_path}")
                os.remove(ytdlp_path)
        except Exception as e:
            logging.warning(f"Error checking existing symlink: {e}")
    
    # Try to download yt-dlp
    logging.info(f"Downloading yt-dlp from {YT_DLP_URL}")
    try:
        # Create SSL context that doesn't verify certificates
        # This is needed as some environments may have outdated or missing CA certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Download the file
        urllib.request.urlretrieve(YT_DLP_URL, ytdlp_path)
        logging.info(f"Successfully downloaded yt-dlp to {ytdlp_path}")
        
        # Make it executable
        os.chmod(ytdlp_path, os.stat(ytdlp_path).st_mode | stat.S_IEXEC)
        logging.info("Made yt-dlp executable")
        
        # Verify it's executable
        if os.access(ytdlp_path, os.X_OK):
            logging.info("yt-dlp is now executable")
        else:
            logging.warning("Failed to make yt-dlp executable")
        
        # Copy file to /app/bin if it's a different location (don't use symlinks)
        try:
            # Check if /app/bin exists and is a different location
            app_bin_path = '/app/bin/yt-dlp'
            if os.path.dirname(ytdlp_path) != '/app/bin' and os.path.isdir('/app/bin'):
                # We need to copy the file, not symlink it
                logging.info(f"Copying yt-dlp to {app_bin_path}")
                import shutil
                shutil.copy2(ytdlp_path, app_bin_path)
                os.chmod(app_bin_path, os.stat(app_bin_path).st_mode | stat.S_IEXEC)
                logging.info(f"Successfully copied to {app_bin_path} and made executable")
            
            # Create symbolic links only to system paths (never to /app/bin)
            common_paths = ['/usr/local/bin/yt-dlp', '/usr/bin/yt-dlp']
            for path in common_paths:
                if path == ytdlp_path:
                    # Skip to avoid self-linking
                    logging.info(f"Skipping symlink to self: {path}")
                    continue
                    
                try:
                    dir_path = os.path.dirname(path)
                    if os.path.isdir(dir_path) and os.access(dir_path, os.W_OK):
                        # Only create symlink if directory exists and is writable
                        if os.path.exists(path):
                            os.remove(path)  # Remove existing file/link
                        # Double check that we're not creating a circular reference
                        if os.path.realpath(ytdlp_path) != os.path.realpath(path):
                            os.symlink(ytdlp_path, path)
                            logging.info(f"Created symlink at {path}")
                        else:
                            logging.warning(f"Skipped creating circular symlink at {path}")
                except (PermissionError, OSError) as e:
                    logging.warning(f"Could not create symlink at {path}: {e}")
        except Exception as e:
            logging.warning(f"Error setting up yt-dlp locations: {e}")
        
        logging.info("yt-dlp installation completed successfully!")
        return 0
        
    except Exception as e:
        logging.error(f"Failed to install yt-dlp: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())