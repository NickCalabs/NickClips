import os
import logging
from flask import Flask, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the Base class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///videos.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure upload paths
app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 1024 * 1024 * 1024))  # Default: 1GB max upload size
app.config["ALLOWED_EXTENSIONS"] = {"mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"}

# Video processing configuration
app.config["MAX_VIDEOS_PER_USER"] = int(os.environ.get("MAX_VIDEOS_PER_USER", 50))
app.config["CONCURRENT_PROCESSING"] = int(os.environ.get("CONCURRENT_PROCESSING", 1))

# yt-dlp configuration
app.config["YT_DLP_PROXY"] = os.environ.get("YT_DLP_PROXY", "")
app.config["YT_DLP_RATE_LIMIT"] = os.environ.get("YT_DLP_RATE_LIMIT", "")
app.config["YT_DLP_MAX_DURATION"] = int(os.environ.get("YT_DLP_MAX_DURATION", 3600))  # 1 hour default

# Ensure upload directory exists with proper permissions
upload_base = app.config["UPLOAD_FOLDER"]
os.makedirs(upload_base, exist_ok=True)

# Create subdirectories for different types of files
subdirs = ["thumbnails", "processed", "original", "hls"]
for subdir in subdirs:
    subdir_path = os.path.join(upload_base, subdir)
    os.makedirs(subdir_path, exist_ok=True)
    # Ensure proper permissions (important for NAS/NFS access)
    os.chmod(subdir_path, 0o755)  # rwxr-xr-x

# Initialize the database
db.init_app(app)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Import and register routes after app creation to avoid circular imports
with app.app_context():
    # Check if necessary ENUM types exist in the database
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    
    # Function to check if ENUM types exist
    def create_enum_if_not_exists(name, values):
        try:
            # Check if the ENUM type already exists
            result = db.session.execute(text(
                "SELECT 1 FROM pg_type WHERE typname = :typename"
            ), {"typename": name})
            
            if result.first() is None:
                # Create the ENUM type if it doesn't exist
                db.session.execute(text(
                    f"CREATE TYPE {name} AS ENUM {str(tuple(values))}"
                ))
                db.session.commit()
                logging.info(f"Created ENUM type '{name}'")
            else:
                logging.info(f"ENUM type '{name}' already exists")
        except Exception as e:
            logging.warning(f"Error handling ENUM type '{name}': {e}")
            db.session.rollback()
    
    # Create ENUM types if they don't exist
    create_enum_if_not_exists('source_types', ['upload', 'link'])
    create_enum_if_not_exists('video_statuses', ['pending', 'downloading', 'processing', 'completed', 'failed'])
    create_enum_if_not_exists('queue_statuses', ['queued', 'processing', 'completed', 'failed'])
    
    # Import models and create tables
    import models
    db.create_all()
    
    # Import and register routes
    from routes import register_routes
    register_routes(app)
    
    # Import and start background processing
    from video_processor import init_processor
    init_processor()

# Add context processor for global template variables
@app.context_processor
def inject_globals():
    import datetime
    return {'now': datetime.datetime.now()}
