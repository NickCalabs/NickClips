import os
import json
import uuid
import datetime
import logging
from flask import request, render_template, redirect, url_for, jsonify, flash, send_from_directory
from werkzeug.utils import secure_filename
from app import db, csrf
from models import User, Video, ProcessingQueue
from downloader import validate_url, queue_download
import video_processor
from forms import LoginForm, RegistrationForm
from flask_login import login_user, logout_user, current_user, login_required

# Setup logging
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {"mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"}

def register_routes(app):
    """Register all routes with the Flask app"""
    
    @app.route('/')
    def index():
        """Home page with upload form"""
        return render_template('index.html')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Admin dashboard to list, rename, and delete videos"""
        if current_user.is_authenticated:
            if current_user.is_admin:
                # Admin sees all videos
                videos = Video.query.order_by(Video.created_at.desc()).all()
            else:
                # Regular users see only their videos
                videos = Video.query.filter_by(user_id=current_user.id).order_by(Video.created_at.desc()).all()
            return render_template('dashboard.html', videos=videos)
        return redirect(url_for('login'))
    
    @app.route('/api/upload', methods=['POST'])
    @csrf.exempt
    def upload_file():
        """Handle direct file upload"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': 'File type not allowed. Supported formats: MP4, MOV, AVI, MKV, WEBM, FLV, WMV'}), 400
            
            # Check upload folder exists
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'original')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Create a unique filename
            original_filename = secure_filename(file.filename)
            filename = f"{uuid.uuid4().hex}_{original_filename}"
            file_path = os.path.join(upload_dir, filename)
            
            # Save the file
            try:
                file.save(file_path)
                
                # Verify file saved correctly
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    return jsonify({'error': 'Failed to save uploaded file'}), 500
            except Exception as e:
                logger.error(f"Error saving uploaded file: {e}")
                return jsonify({'error': f'Error saving file: {str(e)}'}), 500
            
            # Extract title from filename
            title = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
            
            # Create video entry in database
            video = Video(
                title=title,
                original_path=file_path,
                source_type='upload',
                status='pending',
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(video)
            db.session.commit()
            
            # Add to processing queue
            queue_item = ProcessingQueue(video_id=video.id, priority=1)
            db.session.add(queue_item)
            db.session.commit()
            
            # Start processing
            video_processor.process_next()
            
            return jsonify({
                'message': 'Video uploaded successfully',
                'slug': video.slug,
                'redirect': url_for('view_video', slug=video.slug)
            }), 200
            
        except Exception as e:
            logger.error(f"Unexpected error in upload_file: {e}")
            return jsonify({'error': 'Server error occurred during upload'}), 500
    
    @app.route('/api/download', methods=['POST'])
    @csrf.exempt
    def download_video():
        """Handle video download from URL"""
        try:
            data = request.json
            if not data:
                return jsonify({'error': 'Invalid JSON data'}), 400
                
            url = data.get('url')
            
            if not url:
                return jsonify({'error': 'No URL provided'}), 400
            
            # Skip if URL is from our own domain
            if 'replit.dev' in url.lower() or 'repl.co' in url.lower():
                return jsonify({'error': 'Cannot download from our own domain'}), 400
            
            # Validate URL
            if not validate_url(url):
                return jsonify({'error': 'Invalid or unsupported URL'}), 400
            
            # Create video entry in database
            video = Video(
                source_url=url,
                source_type='link',
                status='downloading',
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(video)
            db.session.commit()
            
            # Queue download in background
            queue_download(video.id, url)
            
            return jsonify({
                'message': 'Download queued successfully',
                'slug': video.slug,
                'redirect': url_for('dashboard')
            }), 200
            
        except Exception as e:
            logger.error(f"Unexpected error in download_video: {e}")
            return jsonify({'error': 'Server error occurred during download request'}), 500
    
    @app.route('/video/<slug>')
    def view_video(slug):
        """Public video view page"""
        video = Video.query.filter_by(slug=slug).first_or_404()
        
        # Increment view count
        video.views += 1
        db.session.commit()
        
        return render_template('video.html', video=video)
    
    @app.route('/api/video/<slug>')
    @csrf.exempt
    def get_video_status(slug):
        """API endpoint to check video processing status"""
        video = Video.query.filter_by(slug=slug).first_or_404()
        return jsonify(video.to_dict())
    
    @app.route('/api/video/<slug>/update', methods=['POST'])
    @csrf.exempt
    @login_required
    def update_video(slug):
        """API endpoint to update video title and description"""
        video = Video.query.filter_by(slug=slug).first_or_404()
        
        # Check if user is authorized to update this video
        if not current_user.is_admin and video.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
            
        data = request.json
        
        if 'title' in data:
            video.title = data['title']
        if 'description' in data:
            video.description = data['description']
        
        db.session.commit()
        return jsonify({'success': True, 'video': video.to_dict()})
    
    @app.route('/api/video/<slug>', methods=['DELETE'])
    @csrf.exempt
    @login_required
    def delete_video(slug):
        """API endpoint to delete a video"""
        video = Video.query.filter_by(slug=slug).first_or_404()
        
        # Check if user is authorized to delete this video
        if not current_user.is_admin and video.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete associated files - improved error handling
        try:
            # Make sure we have the correct paths within the upload folder
            upload_folder = app.config['UPLOAD_FOLDER']
            
            # Delete original file
            if video.original_path:
                # Get filename only
                original_filename = os.path.basename(video.original_path)
                original_path = os.path.join(upload_folder, 'original', original_filename)
                if os.path.exists(original_path):
                    os.remove(original_path)
                    logger.info(f"Deleted original file: {original_path}")
                elif os.path.exists(video.original_path):  # Try the stored path directly
                    os.remove(video.original_path)
                    logger.info(f"Deleted original file: {video.original_path}")
                else:
                    logger.warning(f"Could not find original file: {video.original_path}")
            
            # Delete processed file
            if video.processed_path:
                processed_filename = os.path.basename(video.processed_path)
                processed_path = os.path.join(upload_folder, 'processed', processed_filename)
                if os.path.exists(processed_path):
                    os.remove(processed_path)
                    logger.info(f"Deleted processed file: {processed_path}")
                elif os.path.exists(video.processed_path):  # Try the stored path directly
                    os.remove(video.processed_path)
                    logger.info(f"Deleted processed file: {video.processed_path}")
                else:
                    logger.warning(f"Could not find processed file: {video.processed_path}")
            
            # Delete thumbnail file
            if video.thumbnail_path:
                thumbnail_filename = os.path.basename(video.thumbnail_path)
                thumbnail_path = os.path.join(upload_folder, 'thumbnails', thumbnail_filename)
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
                    logger.info(f"Deleted thumbnail file: {thumbnail_path}")
                elif os.path.exists(video.thumbnail_path):  # Try the stored path directly
                    os.remove(video.thumbnail_path)
                    logger.info(f"Deleted thumbnail file: {video.thumbnail_path}")
                else:
                    logger.warning(f"Could not find thumbnail file: {video.thumbnail_path}")
            
            # Delete HLS files if they exist
            if video.hls_path:
                # Try both potential HLS directory paths
                hls_dir = os.path.dirname(video.hls_path)
                hls_slug = os.path.basename(hls_dir)
                alt_hls_dir = os.path.join(upload_folder, 'hls', hls_slug)
                
                # Try stored path first
                if os.path.exists(hls_dir) and os.path.isdir(hls_dir):
                    for file in os.listdir(hls_dir):
                        file_path = os.path.join(hls_dir, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    os.rmdir(hls_dir)
                    logger.info(f"Deleted HLS directory: {hls_dir}")
                # Try alternative path
                elif os.path.exists(alt_hls_dir) and os.path.isdir(alt_hls_dir):
                    for file in os.listdir(alt_hls_dir):
                        file_path = os.path.join(alt_hls_dir, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    os.rmdir(alt_hls_dir)
                    logger.info(f"Deleted HLS directory: {alt_hls_dir}")
                else:
                    logger.warning(f"Could not find HLS directory: {hls_dir} or {alt_hls_dir}")
        except Exception as e:
            logger.error(f"Error deleting files for video {video.slug}: {str(e)}")
            # Continue with database deletion even if file deletion fails
        
        # Delete queue items first to avoid foreign key constraint errors
        try:
            # Delete all queue items associated with this video first
            queue_items = ProcessingQueue.query.filter_by(video_id=video.id).all()
            for item in queue_items:
                db.session.delete(item)
            db.session.commit()
            logger.info(f"Deleted {len(queue_items)} queue items for video {video.slug}")
            
            # Then delete the video
            db.session.delete(video)
            db.session.commit()
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Database error during video deletion: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Database error while deleting video'}), 500
    
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        """Serve uploaded files"""
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    @app.route('/uploads/thumbnails/<filename>')
    def serve_thumbnail(filename):
        """Serve thumbnail files"""
        return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails'), filename)
    
    @app.route('/uploads/processed/<filename>')
    def serve_processed_video(filename):
        """Serve processed video files"""
        return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'processed'), filename)
    
    @app.route('/uploads/hls/<path:filename>')
    def serve_hls(filename):
        """Serve HLS stream files"""
        return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'hls'), filename)
        
    # Authentication routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login page"""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                flash('Invalid username or password', 'danger')
                return redirect(url_for('login'))
            
            login_user(user, remember=form.remember_me.data)
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to requested page or dashboard
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard')
            return redirect(next_page)
            
        return render_template('login.html', form=form)
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """User registration page"""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = RegistrationForm()
        if form.validate_on_submit():
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            
            # Make the first user an admin
            if User.query.count() == 0:
                user.is_admin = True
            
            db.session.add(user)
            db.session.commit()
            
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
            
        return render_template('register.html', form=form)
    
    @app.route('/logout')
    def logout():
        """User logout"""
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))
        
    @app.route('/profile', methods=['GET'])
    @login_required
    def profile():
        """User profile and settings page"""
        from forms import ChangePasswordForm, ThemePreferenceForm
        password_form = ChangePasswordForm()
        theme_form = ThemePreferenceForm()
        return render_template('profile.html', form=password_form, theme_form=theme_form)
    
    @app.route('/profile/change-password', methods=['POST'])
    @login_required
    def change_password():
        """Change user password"""
        from forms import ChangePasswordForm
        form = ChangePasswordForm()
        
        if form.validate_on_submit():
            # Validate current password
            if not current_user.check_password(form.current_password.data):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('profile', _anchor='security-section'))
            
            # Update password
            current_user.set_password(form.new_password.data)
            db.session.commit()
            
            flash('Password updated successfully.', 'success')
            return redirect(url_for('profile', _anchor='security-section'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{getattr(form, field).label.text}: {error}', 'danger')
            return redirect(url_for('profile', _anchor='security-section'))
            
    @app.route('/profile/update-theme', methods=['POST'])
    @login_required
    def update_theme():
        """Update theme preference"""
        from forms import ThemePreferenceForm
        form = ThemePreferenceForm()
        
        if form.validate_on_submit():
            theme_preference = form.theme.data
            # Note: In a real application, we would save this to the user's preferences in the database
            # For now, we'll just use local storage which is updated via JavaScript
            
            flash('Theme preferences saved successfully.', 'success')
            return redirect(url_for('profile', _anchor='appearance-section'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{getattr(form, field).label.text}: {error}', 'danger')
            return redirect(url_for('profile', _anchor='appearance-section'))
