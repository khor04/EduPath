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

    # A hosted Postgres (Supabase) closes connections that sit idle, but
    # the pool keeps handing them out, so the first request after a
    # quiet spell hits a dead connection and 500s -- then works on retry
    # once the pool has discarded it. pre_ping tests a connection before
    # use and transparently replaces a dead one; recycle retires
    # connections before the server's idle cutoff.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Outbound email (verification codes, password resets) goes through
    # Brevo's HTTPS transactional API (routes/auth.py:send_email_via_brevo),
    # not SMTP -- Render blocks outbound SMTP (ports 25/465/587) on free
    # web services, confirmed 2026-09-22 in production
    # (https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports).
    # BREVO_SENDER_EMAIL must be a sender verified in the Brevo dashboard.
    BREVO_API_KEY = os.getenv("BREVO_API_KEY")
    BREVO_SENDER_NAME = "EduPath System"
    BREVO_SENDER_EMAIL = "khorch0425@gmail.com"

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