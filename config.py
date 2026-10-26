import os
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'campus-smart-lost-found-secret-key-2026')
    
    # MySQL Database Settings
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'campus_lost_found')
    
    # SQLite Fallback Path
    SQLITE_PATH = os.path.join(BASE_DIR, 'campus_lost_found.db')
    
    # File Upload Settings
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max limit
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    # Session Cookie Hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Permitted college email domains for student registrations
    ALLOWED_EMAIL_DOMAINS = [
        'campus.edu', 'acharya.ac.in', 'edu', 'ac.in', 'college.edu', 'student.edu'
    ]
