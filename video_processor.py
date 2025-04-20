import os
import time
import logging
import threading
import subprocess
import json
from datetime import datetime
import shutil
from app import db
from models import Video, ProcessingQueue

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Video processing thread and control flag
processing_thread = None
should_stop = False
processing_lock = threading.Lock()

def init_processor():
    """Initialize the video processor"""
    global processing_thread, should_stop
    
    should_stop = False
    
    if processing_thread is None or not processing_thread.is_alive():
        processing_thread = threading.Thread(target=processor_worker)
        processing_thread.daemon = True
        processing_thread.start()
        logger.info("Video processor initialized")

def stop_processor():
    """Stop the video processor thread"""
    global should_stop
    should_stop = True
    logger.info("Video processor stopping...")

def processor_worker():
    """Background worker that processes videos in the queue"""
    global should_stop
    
    logger.info("Video processor worker started")
    
    while not should_stop:
        # Check if there are any videos to process
        processed_any = process_next()
        
        # If nothing was processed, sleep for a bit
        if not processed_any:
            time.sleep(5)
    
    logger.info("Video processor worker stopped")

def process_next():
    """Process the next video in the queue"""
    from app import app
    
    with app.app_context():
        # Find the next queued video with highest priority
        with processing_lock:
            queue_item = ProcessingQueue.query.filter_by(status='queued').order_by(
                ProcessingQueue.priority.desc(),
                ProcessingQueue.created_at.asc()
            ).first()
            
            if not queue_item:
                return False
            
            # Mark as processing
            queue_item.status = 'processing'
            queue_item.started_at = datetime.utcnow()
            
            video = Video.query.get(queue_item.video_id)
            if video:
                video.status = 'processing'
            
            db.session.commit()
        
        # Process the video outside the lock
        try:
            if video:
                logger.info(f"Processing video {video.id} ({video.slug})")
                
                # Process the video
                success = process_video(video, app.config['UPLOAD_FOLDER'])
                
                # Update the status
                if success:
                    queue_item.status = 'completed'
                    queue_item.completed_at = datetime.utcnow()
                    video.status = 'completed'
                else:
                    queue_item.status = 'failed'
                    video.status = 'failed'
                    video.error = "Failed to process video"
                
                db.session.commit()
                return True
            
        except Exception as e:
            logger.exception(f"Error processing video: {e}")
            
            # Update the status
            queue_item.status = 'failed'
            if video:
                video.status = 'failed'
                video.error = str(e)
            
            db.session.commit()
            return True
    
    return False

def process_video(video, upload_folder):
    """Process a video - generate thumbnail and transcode"""
    try:
        # Make sure we have an original file to process
        if not video.original_path or not os.path.exists(video.original_path):
            raise Exception("Original video file not found")
        
        # Create output paths
        processed_dir = os.path.join(upload_folder, 'processed')
        thumbnail_dir = os.path.join(upload_folder, 'thumbnails')
        hls_dir = os.path.join(upload_folder, 'hls', video.slug)
        
        os.makedirs(processed_dir, exist_ok=True)
        os.makedirs(thumbnail_dir, exist_ok=True)
        os.makedirs(hls_dir, exist_ok=True)
        
        mp4_output = os.path.join(processed_dir, f"{video.slug}.mp4")
        thumbnail_output = os.path.join(thumbnail_dir, f"{video.slug}.jpg")
        hls_playlist = os.path.join(hls_dir, "playlist.m3u8")
        
        # Get video information
        video_info = get_video_info(video.original_path)
        
        # Update the video with metadata
        video.duration = float(video_info.get('duration', 0))
        video.width = int(video_info.get('width', 0))
        video.height = int(video_info.get('height', 0))
        video.size = os.path.getsize(video.original_path)
        
        if not video.title and 'filename' in video_info:
            video.title = os.path.splitext(video_info['filename'])[0]
        
        db.session.commit()
        
        # Generate thumbnail
        extract_thumbnail(video.original_path, thumbnail_output)
        video.thumbnail_path = os.path.join('thumbnails', f"{video.slug}.jpg")
        
        # Transcode to MP4
        transcode_to_mp4(video.original_path, mp4_output)
        video.processed_path = os.path.join('processed', f"{video.slug}.mp4")
        
        # Create HLS stream
        create_hls_stream(mp4_output, hls_dir)
        video.hls_path = os.path.join('hls', video.slug, 'playlist.m3u8')
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.exception(f"Error processing video {video.id}: {e}")
        video.error = str(e)
        db.session.commit()
        return False

def get_video_info(video_path):
    """Get video metadata using FFprobe"""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Extract relevant information
        info = {
            'filename': os.path.basename(video_path)
        }
        
        # Get duration from format
        if 'format' in data and 'duration' in data['format']:
            info['duration'] = float(data['format']['duration'])
        
        # Get video stream information
        video_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        if video_stream:
            info['width'] = int(video_stream.get('width', 0))
            info['height'] = int(video_stream.get('height', 0))
            
            # Calculate duration from framerate and frames if not available
            if 'duration' not in info and 'r_frame_rate' in video_stream and 'nb_frames' in video_stream:
                fps_parts = video_stream['r_frame_rate'].split('/')
                if len(fps_parts) == 2:
                    fps = float(fps_parts[0]) / float(fps_parts[1])
                    frames = int(video_stream['nb_frames'])
                    info['duration'] = frames / fps
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return {}

def extract_thumbnail(video_path, output_path):
    """Extract a thumbnail from the video at the 5 second mark or 25% point"""
    try:
        # Get video duration
        info = get_video_info(video_path)
        duration = float(info.get('duration', 0))
        
        # Extract at 5 seconds or 25% of duration if less than 20 seconds
        seek_time = min(5, max(1, duration * 0.25)) if duration > 0 else 0
        
        logger.debug(f"Extracting thumbnail for {video_path} at {seek_time}s to {output_path}")
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output files
                '-ss', str(seek_time),  # Seek position
                '-i', video_path,  # Input file
                '-vframes', '1',  # Extract one frame
                '-q:v', '2',  # Quality (2 is high, lower is better)
                output_path
            ]
            
            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"ffmpeg thumbnail extraction returned error: {result.stderr}")
                raise Exception(f"ffmpeg error: {result.stderr}")
            
            # Verify the thumbnail was created
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.warning(f"Thumbnail file not created or is empty: {output_path}")
                raise Exception("Thumbnail generation failed, output file is empty or missing")
                
            logger.info(f"Thumbnail successfully created at {output_path}")
            return True
            
        except Exception as thumbnail_error:
            # Create a generic placeholder thumbnail
            logger.warning(f"Thumbnail extraction failed: {thumbnail_error}")
            logger.info("FALLBACK: Creating a generic placeholder thumbnail")
            
            # Create a simple 320x180 black image with text as a fallback
            try:
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-f', 'lavfi',
                    '-i', 'color=c=black:s=320x180',
                    '-vframes', '1',
                    '-vf', "drawtext=text='Video':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2",
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    # If even the placeholder creation failed, use a more direct method
                    logger.warning("Placeholder creation failed, using direct file write method")
                    
                    # Create a minimal valid JPEG file (1x1 pixel, black)
                    # This is a raw JPEG header and data that represents a minimal 1x1 black pixel
                    jpeg_data = bytes([
                        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48,
                        0x00, 0x48, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43, 0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
                        0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
                        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20,
                        0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29, 0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27,
                        0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
                        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x14, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x09, 0xFF, 0xC4, 0x00, 0x14,
                        0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x54, 0x7F, 0xFF, 0xD9
                    ])
                    
                    with open(output_path, 'wb') as f:
                        f.write(jpeg_data)
                
                logger.info(f"Fallback thumbnail created at {output_path}")
                return True
                
            except Exception as fallback_error:
                logger.error(f"Failed to create fallback thumbnail: {fallback_error}")
                return False
        
    except Exception as e:
        logger.error(f"Error in extract_thumbnail: {e}")
        return False

def transcode_to_mp4(input_path, output_path):
    """Transcode video to MP4 format with H.264 video and AAC audio"""
    try:
        logger.debug(f"Transcoding {input_path} to MP4 at {output_path}")
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files
            '-i', input_path,  # Input file
            '-c:v', 'libx264',  # Video codec
            '-preset', 'medium',  # Compression preset
            '-crf', '22',  # Quality (lower is better)
            '-c:a', 'aac',  # Audio codec
            '-b:a', '128k',  # Audio bitrate
            '-movflags', '+faststart',  # Optimize for web streaming
            output_path
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Check if FFmpeg succeeded
            if result.returncode != 0:
                logger.warning(f"FFmpeg transcoding failed with error: {result.stderr}")
                raise Exception(f"ffmpeg transcoding error: {result.stderr}")
            
            # Verify the output file was created
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.warning(f"Transcoded file not created or is empty: {output_path}")
                raise Exception("Transcoding failed, output file is empty or missing")
                
            logger.info(f"Transcoding successfully completed at {output_path}")
            return True
            
        except Exception as ffmpeg_error:
            # FFmpeg failed - use fallback method
            logger.warning(f"Transcoding failed, using fallback: {ffmpeg_error}")
            
            # Use a direct file copy as fallback
            logger.info(f"FALLBACK: Copying original file to {output_path} since transcoding failed")
            shutil.copy2(input_path, output_path)
            
            # Verify the fallback copy worked
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Fallback copy successful: {output_path}")
                return True
            else:
                logger.error(f"Fallback copy also failed for {input_path}")
                return False
    
    except Exception as e:
        logger.error(f"Error in transcode_to_mp4: {e}")
        return False

def create_hls_stream(input_path, output_dir):
    """Create HLS stream for adaptive bitrate streaming"""
    try:
        playlist_path = os.path.join(output_dir, 'playlist.m3u8')
        logger.debug(f"Creating HLS stream from {input_path} to {playlist_path}")
        
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files
            '-i', input_path,  # Input file
            '-profile:v', 'baseline',  # H.264 profile
            '-level', '3.0',  # H.264 level
            '-start_number', '0',  # Start number for segments
            '-hls_time', '4',  # Segment duration in seconds (reduced from 10)
            '-hls_list_size', '0',  # All segments in playlist
            '-hls_segment_type', 'mpegts',  # More compatible segment type
            '-hls_flags', 'independent_segments',  # Each segment can be decoded independently
            '-g', '48',  # Keyframe interval (reduced for more stable playback)
            '-sc_threshold', '0',  # Disable scene change detection
            '-c:v', 'libx264',  # Video codec
            '-c:a', 'aac',  # Audio codec
            '-b:a', '128k',  # Audio bitrate
            '-f', 'hls',  # Format
            playlist_path
        ]
        
        try:
            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"ffmpeg HLS creation returned error: {result.stderr}")
                raise Exception(f"ffmpeg HLS creation error: {result.stderr}")
            
            # Verify the playlist file was created
            if not os.path.exists(playlist_path) or os.path.getsize(playlist_path) == 0:
                logger.warning(f"HLS playlist not created or is empty: {playlist_path}")
                raise Exception("HLS creation failed, playlist file is empty or missing")
                
            logger.info(f"HLS stream successfully created at {playlist_path}")
            return True
            
        except Exception as ffmpeg_error:
            # Create a simple playlist that just points to the MP4 file
            logger.warning(f"HLS creation failed with FFmpeg: {ffmpeg_error}")
            logger.info(f"FALLBACK: Creating a simple HLS playlist for {input_path}")
            
            # Get relative path to the mp4 file from the HLS directory
            # Typically will be something like "../processed/slug.mp4"
            rel_path = os.path.relpath(input_path, output_dir)
            
            # Create a very simple HLS playlist that just references the original MP4
            # This won't support adaptive streaming but will allow playback
            playlist_content = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:0
#EXT-X-MEDIA-SEQUENCE:1
#EXTINF:0,
{rel_path}
#EXT-X-ENDLIST
"""
            try:
                with open(playlist_path, 'w') as f:
                    f.write(playlist_content)
                
                logger.info(f"FALLBACK HLS playlist created successfully at {playlist_path}")
                return True
            except Exception as fallback_error:
                logger.error(f"Failed to create fallback HLS playlist: {fallback_error}")
                return False
    
    except Exception as e:
        logger.error(f"Error in create_hls_stream: {e}")
        return False
