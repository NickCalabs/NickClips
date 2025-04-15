import os
import sys
import logging
from app import app, db
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    """Run database migrations manually"""
    with app.app_context():
        try:
            # Check if user_id column exists in video table
            result = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='video' AND column_name='user_id'"
            ))
            
            # If user_id doesn't exist, add it
            if result.rowcount == 0:
                logger.info("Adding user_id column to video table...")
                db.session.execute(text(
                    "ALTER TABLE video ADD COLUMN user_id INTEGER REFERENCES \"user\" (id) ON DELETE SET NULL"
                ))
                db.session.commit()
                logger.info("Migration completed successfully!")
            else:
                logger.info("user_id column already exists in video table")
            
            # Additional migrations can be added here
                
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            db.session.rollback()
            sys.exit(1)

if __name__ == "__main__":
    run_migrations()