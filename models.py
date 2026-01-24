import uuid
import datetime
import random
import string
from app import db
from sqlalchemy import Enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

def generate_slug():
    """Generate a random slug for video URLs"""
    return uuid.uuid4().hex[:8]

def generate_api_key():
    """Generate a random API key"""
    return 'nc_' + uuid.uuid4().hex

def generate_referral_code():
    """Generate a random referral code in format XXXX-XXXX"""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"{part1}-{part2}"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    api_key = db.Column(db.String(64), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # User-Video relationship
    videos = db.relationship('Video', backref='owner', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def regenerate_api_key(self):
        """Generate a new API key for this user"""
        self.api_key = generate_api_key()
        return self.api_key


class ReferralCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, default=generate_referral_code)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_codes')
    used_by = db.relationship('User', foreign_keys=[used_by_id], backref='used_code')

    def __repr__(self):
        return f'<ReferralCode {self.code}>'

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by.username if self.created_by else None,
            'used_by': self.used_by.username if self.used_by else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'is_used': self.used_by_id is not None
        }


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

    # Visibility - public videos appear on user's profile
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    # Trimming parameters (for clipping videos)
    trim_start = db.Column(db.Float, nullable=True)  # Start time in seconds
    trim_end = db.Column(db.Float, nullable=True)    # End time in seconds

    # Expiration settings
    expires_at = db.Column(db.DateTime, nullable=True)
    expiration_action = db.Column(db.String(10), nullable=True)  # 'delete' or 'hide'

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
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'expiration_action': self.expiration_action
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
