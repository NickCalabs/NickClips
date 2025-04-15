import uuid
import datetime
from app import db
from sqlalchemy import Enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

def generate_slug():
    """Generate a random slug for video URLs"""
    return uuid.uuid4().hex[:8]
    
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # User-Video relationship
    videos = db.relationship('Video', backref='owner', lazy='dynamic', cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(10), unique=True, default=generate_slug)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    # Owner reference
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Video file paths
    original_path = db.Column(db.String(255), nullable=True)
    processed_path = db.Column(db.String(255), nullable=True)
    hls_path = db.Column(db.String(255), nullable=True)
    thumbnail_path = db.Column(db.String(255), nullable=True)
    
    # Video metadata
    duration = db.Column(db.Float, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    size = db.Column(db.Integer, nullable=True)  # File size in bytes
    
    # Source info
    source_url = db.Column(db.String(1024), nullable=True)  # URL if downloaded from the web
    source_type = db.Column(Enum('upload', 'link', name='source_types'), nullable=False)
    
    # Processing status
    status = db.Column(
        Enum('pending', 'downloading', 'processing', 'completed', 'failed', name='video_statuses'),
        default='pending',
        nullable=False
    )
    error = db.Column(db.Text, nullable=True)  # Error message if processing failed
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, 
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )
    
    # View count
    views = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Video {self.id}: {self.title or "Untitled"}>'
    
    def to_dict(self):
        """Convert the video object to a dictionary for JSON responses"""
        data = {
            'id': self.id,
            'slug': self.slug,
            'title': self.title or "Untitled",
            'description': self.description,
            'thumbnail_path': f"/uploads/thumbnails/{self.slug}.jpg" if self.thumbnail_path else None,
            'duration': self.duration,
            'width': self.width,
            'height': self.height,
            'size': self.size,
            'status': self.status,
            'views': self.views,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id
        }
        
        # Add username if the video has an owner
        if self.owner:
            data['username'] = self.owner.username
            
        return data

class ProcessingQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id', ondelete='CASCADE'), nullable=False)
    priority = db.Column(db.Integer, default=0)  # Higher number = higher priority
    status = db.Column(
        Enum('queued', 'processing', 'completed', 'failed', name='queue_statuses'),
        default='queued',
        nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    video = db.relationship('Video', backref=db.backref('queue_items', lazy=True))
    
    def __repr__(self):
        return f'<ProcessingQueue {self.id}: Video {self.video_id}>'
