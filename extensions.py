from flask import request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def rate_limit_key():
    """
    Who a rate limit counts against, unless a route says otherwise.

    Logged-in users are counted per ACCOUNT, not per IP: a whole class on
    the same campus Wi-Fi (or phones behind one mobile-network IP) shares a
    single public IP, and per-IP counting would let one student use up
    everyone else's allowance. Visitors without an account (login, signup,
    contact...) can only be told apart by IP, so they stay per IP.
    """
    if current_user.is_authenticated:
        return f"user:{current_user.get_id()}"
    return get_remote_address()


def ip_and_email_key():
    """
    Per IP AND the email typed into the form -- for the sign-in forms. Lets a
    classroom sharing one IP each use their own account's allowance, while
    repeated attempts on ONE account (password guessing) are still stopped.
    Always paired with a looser plain-per-IP limit on the same route, so one
    machine can't get around it by cycling through different emails.
    """
    email = (request.form.get("email") or "").strip().lower()
    return f"{get_remote_address()}|{email}"


db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=rate_limit_key, default_limits=["200 per day", "50 per hour"])
