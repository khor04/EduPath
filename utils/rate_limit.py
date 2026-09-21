"""
One friendly response for every rate limit in the app (HTTP 429), instead of
Flask-Limiter's bare "429 Too Many Requests" page.

Two kinds of request can hit a limit, and each needs a different answer:

  * A browser loading a page or submitting a normal form (e.g. the login form)
    gets a proper page that says how long to wait.
  * The JavaScript on our pages (chat widget, Grade Tracker, share-link dialog,
    ...) calls the server with fetch() and expects JSON. It gets the same
    {"success": false, "message": ...} shape those scripts already display, so
    the student sees the message in place instead of "Something went wrong".

Which one is decided by what the request asks for: a browser navigation sends
"Accept: text/html,...", while fetch() sends "Accept: */*" -- so preferring JSON
whenever HTML isn't asked for explicitly catches every fetch() call, including
ones whose URL doesn't start with /api/.
"""
import math
import time
from urllib.parse import urlparse

from flask import jsonify, render_template, request, url_for
from flask_login import current_user

from extensions import limiter


def seconds_until_retry():
    """Seconds until the limit that was just hit resets, or None if unknown."""
    current = limiter.current_limit
    if current is None or not current.reset_at:
        return None
    return max(1, math.ceil(current.reset_at - time.time()))


def describe_wait(seconds):
    """'about 12 minutes' / 'about a minute' / 'a few seconds', for messages."""
    if seconds is None:
        return "a little while"
    if seconds < 45:
        return "a few seconds"
    minutes = round(seconds / 60)
    if minutes <= 1:
        return "about a minute"
    if minutes < 60:
        return f"about {minutes} minutes"
    hours = round(minutes / 60)
    return "about an hour" if hours <= 1 else f"about {hours} hours"


def _wants_json():
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"


def _safe_back_url(home):
    """
    The page they came from, but only if it is on this site (never an open
    redirect). For a blocked form POST (e.g. login) that page is the form
    itself, which is exactly where they should go back to. For a blocked page
    load, going "back" to the same page would just hit the limit again.
    """
    ref = request.referrer
    if not ref or urlparse(ref).netloc != request.host:
        return home
    if request.method == "GET" and urlparse(ref).path == request.path:
        return home
    return ref


def _home_url():
    if current_user.is_authenticated:
        return url_for("admin.admin_stats") if current_user.is_admin else url_for("dashboard.dashboard")
    return url_for("landing")


def handle_rate_limited(error):
    seconds = seconds_until_retry()
    wait = describe_wait(seconds)
    headers = {"Retry-After": str(seconds)} if seconds else {}

    if _wants_json():
        body = jsonify({
            "success": False,
            "error": "rate_limited",
            "message": f"You're doing that too often. Please wait {wait} and try again.",
            "retry_after": seconds,
        })
        return body, 429, headers

    home = _home_url()
    page = render_template(
        "rate_limited.html",
        wait=wait,
        back_url=_safe_back_url(home),
        home_url=home,
    )
    return page, 429, headers
