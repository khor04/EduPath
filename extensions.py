from flask import request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
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
csrf = CSRFProtect()
# Applied per ROUTE per key, to every route that doesn't set its own.
# Sized for a student, not an API client: students refresh pages
# constantly (especially while something is loading), and every page
# load also fires background calls of its own -- /api/chat/suggestions
# for the chat widget, /api/benchmark-data on the Dashboard. At the
# old 50/hour, roughly fifty page loads in an hour was enough to start
# silently breaking those widgets during ordinary use, which is well
# within what one student clicking around can do.
#
# These are a backstop against runaway loops and scraping, NOT a
# usage budget. Anything genuinely expensive -- sending email, guessing
# passwords, or spending Gemini quota -- sets its own, much tighter
# limit at the route instead (see routes/auth.py, routes/chat.py,
# routes/analysis.py's /generate-ai-plan).
limiter = Limiter(key_func=rate_limit_key, default_limits=["2000 per day", "300 per hour"])
