import os
import json
import uuid
import datetime
import logging
from flask import request, render_template, redirect, url_for, jsonify, flash, send_from_directory
from werkzeug.utils import secure_filename
from app import db
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
    
    @app.route('/upload', methods=['POST'])
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
    
    @app.route('/download', methods=['POST'])
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
                'redirect': url_for('view_video', slug=video.slug)
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
    def get_video_status(slug):
        """API endpoint to check video processing status"""
        video = Video.query.filter_by(slug=slug).first_or_404()
        return jsonify(video.to_dict())
    
    @app.route('/api/video/<slug>/update', methods=['POST'])
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
    
    @app.route('/api/video/<slug>/delete', methods=['POST'])
    @login_required
    def delete_video(slug):
        """API endpoint to delete a video"""
        video = Video.query.filter_by(slug=slug).first_or_404()
        
        # Check if user is authorized to delete this video
        if not current_user.is_admin and video.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete associated files
        if video.original_path and os.path.exists(video.original_path):
            os.remove(video.original_path)
        if video.processed_path and os.path.exists(video.processed_path):
            os.remove(video.processed_path)
        if video.thumbnail_path and os.path.exists(video.thumbnail_path):
            os.remove(video.thumbnail_path)
        
        # Delete HLS files if they exist
        if video.hls_path:
            hls_dir = os.path.dirname(video.hls_path)
            if os.path.exists(hls_dir):
                for file in os.listdir(hls_dir):
                    os.remove(os.path.join(hls_dir, file))
                os.rmdir(hls_dir)
        
        # Delete from database
        db.session.delete(video)
        db.session.commit()
        
        return jsonify({'success': True})
    
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
