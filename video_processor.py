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
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files
            '-ss', str(seek_time),  # Seek position
            '-i', video_path,  # Input file
            '-vframes', '1',  # Extract one frame
            '-q:v', '2',  # Quality (2 is high, lower is better)
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return True
        
    except Exception as e:
        logger.error(f"Error extracting thumbnail: {e}")
        return False

def transcode_to_mp4(input_path, output_path):
    """Transcode video to MP4 format with H.264 video and AAC audio"""
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
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        logger.error(f"Error transcoding to MP4: {e}")
        return False

def create_hls_stream(input_path, output_dir):
    """Create HLS stream for adaptive bitrate streaming"""
    playlist_path = os.path.join(output_dir, 'playlist.m3u8')
    
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
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        logger.error(f"Error creating HLS stream: {e}")
        return False
