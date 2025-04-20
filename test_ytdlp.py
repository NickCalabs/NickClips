#!/usr/bin/env python3
"""
Test script to verify yt-dlp installation and proper path resolution
"""
import os
import sys
import logging
import subprocess
import shutil
import json

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_yt_dlp_path():
    """Get the path to yt-dlp executable, trying multiple options"""
    # Common locations to check for yt-dlp
    locations = [
        # Docker container paths
        '/app/bin/yt-dlp',
        '/usr/local/bin/yt-dlp',
        '/opt/stacks/nickclips/bin/yt-dlp',  # Dockge specific path
        
        # Local development paths
        os.path.join(os.getcwd(), 'bin', 'yt-dlp'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'yt-dlp'),
    ]
    
    # Check each location
    for location in locations:
        if os.path.isfile(location) and os.access(location, os.X_OK):
            logger.info(f"Found executable yt-dlp at: {location}")
            return location
    
    # Try system path via shutil.which
    system_yt_dlp = shutil.which('yt-dlp')
    if system_yt_dlp:
        logger.info(f"Found yt-dlp in system PATH: {system_yt_dlp}")
        return system_yt_dlp
    
    # Log warning about potential issues
    logger.warning("Could not find yt-dlp at common locations, falling back to 'yt-dlp' command. "
                 "This may cause errors if yt-dlp is not in PATH.")
    
    # Default to just 'yt-dlp' and hope it's in the PATH
    return 'yt-dlp'

def test_yt_dlp():
    """Test if yt-dlp is working properly"""
    yt_dlp_path = get_yt_dlp_path()
    logger.info(f"Using yt-dlp from: {yt_dlp_path}")
    
    # Test version output
    try:
        version_output = subprocess.check_output([yt_dlp_path, '--version'], 
                                              stderr=subprocess.STDOUT, 
                                              text=True)
        logger.info(f"yt-dlp version: {version_output.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get yt-dlp version: {e.output}")
        return False
    except FileNotFoundError:
        logger.error(f"yt-dlp executable not found at {yt_dlp_path}")
        return False
    
    # Test extracting video info from a public domain video
    try:
        # Using Big Buck Bunny as a test - it's public domain
        test_url = "https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4"
        logger.info(f"Testing yt-dlp with URL: {test_url}")
        
        # Run yt-dlp with JSON output and skip download
        cmd = [yt_dlp_path, "--dump-json", "--no-download", test_url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"yt-dlp command failed: {result.stderr}")
            return False
            
        if not result.stdout.strip():
            logger.error("yt-dlp returned empty response")
            return False
            
        # Try to parse as JSON
        try:
            video_info = json.loads(result.stdout)
            logger.info(f"Successfully extracted video info: {video_info.get('title', 'Unknown title')}")
            return True
        except json.JSONDecodeError:
            logger.error(f"Could not parse yt-dlp output as JSON: {result.stdout}")
            return False
            
    except Exception as e:
        logger.error(f"Error testing yt-dlp: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting yt-dlp test...")
    if test_yt_dlp():
        logger.info("✓ yt-dlp is working correctly!")
        sys.exit(0)
    else:
        logger.error("✗ yt-dlp test failed. Please check installation and permissions.")
        sys.exit(1)