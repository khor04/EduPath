import os
from dotenv import load_dotenv
import os
import cloudinary

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)
load_dotenv()  # loads variables from .env file

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = "khorch0425@gmail.com"
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = ("EduPath System", "khorch0425@gmail.com")

    # The session cookie carries the login session id and (via Flask-WTF)
    # backs CSRF validation, and this app handles academic transcripts, so
    # it shouldn't be readable by JS or sent over plain HTTP in production.
    # SECURE is opt-in via FLASK_ENV=production (set this in your
    # deployment platform's env vars -- Render/Railway/Fly all give HTTPS
    # by default) rather than always-on, because a browser silently drops
    # a Secure cookie set over plain http://, which would break login on
    # `python app.py` during local development if this defaulted to True.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
    )