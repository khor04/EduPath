import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from extensions import db, limiter
from models.contact import ContactMessage
from utils.rate_limit import describe_wait, handle_rate_limited, seconds_until_retry

info_bp = Blueprint("info", __name__)

# Anyone can post this form without an account, so it gets a limit of its
# own instead of relying on the site-wide default (50/hour per IP). Only
# submissions count -- viewing the page is never limited here.
CONTACT_LIMIT = "5 per hour"

# Server-side limits. Name and email match the column sizes on
# ContactMessage (a longer value would make Postgres reject the insert with
# a 500); the message column is unbounded Text, so this is what stops
# someone posting megabytes of text.
MAX_NAME = 100
MAX_EMAIL = 120
MAX_MESSAGE = 2000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# A field real visitors never see or fill in (hidden by CSS). Bots that
# fill in every input give themselves away.
HONEYPOT_FIELD = "website"


def _validate_contact(form):
    """Trimmed values and a {field: message} dict of problems (empty if valid)."""
    values = {
        "name": (form.get("name") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "message": (form.get("message") or "").strip(),
    }
    errors = {}

    if not values["name"]:
        errors["name"] = "Name is required"
    elif len(values["name"]) > MAX_NAME:
        errors["name"] = f"Name must be {MAX_NAME} characters or fewer"

    if not values["email"]:
        errors["email"] = "Email is required"
    elif len(values["email"]) > MAX_EMAIL:
        errors["email"] = f"Email must be {MAX_EMAIL} characters or fewer"
    elif not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "Invalid email format"

    if not values["message"]:
        errors["message"] = "Message is required"
    elif len(values["message"]) > MAX_MESSAGE:
        errors["message"] = f"Message must be {MAX_MESSAGE} characters or fewer"

    return values, errors


def _render_contact(values=None, errors=None, notice=None, status=200):
    return render_template(
        "contact.html",
        active_page="contact",
        values=values or {},
        errors=errors or {},
        notice=notice,
        limits={"name": MAX_NAME, "email": MAX_EMAIL, "message": MAX_MESSAGE},
    ), status


@info_bp.route("/about")
def about():
    return render_template("about.html", active_page="about")


@info_bp.route("/contact", methods=["GET", "POST"])
@limiter.limit(CONTACT_LIMIT, methods=["POST"])
def contact():

    if request.method == "POST":

        # Looks exactly like success to the sender, but nothing is stored.
        if request.form.get(HONEYPOT_FIELD):
            flash("Message sent successfully!", "success")
            return redirect(url_for("info.contact"))

        values, errors = _validate_contact(request.form)
        if errors:
            return _render_contact(values, errors, status=400)

        db.session.add(ContactMessage(
            name=values["name"],
            email=values["email"],
            message=values["message"],
            user_id=current_user.user_id if current_user.is_authenticated else None
        ))
        db.session.commit()

        flash("Message sent successfully!", "success")

        return redirect(url_for("info.contact"))

    return _render_contact()


@info_bp.errorhandler(429)
def contact_rate_limited(error):
    # Takes priority over the site-wide 429 page for every route in this
    # blueprint, so hand anything that isn't the contact form (/about,
    # /privacy hitting the default limit) back to the site-wide page. For the
    # contact form, re-show it with what they typed, so nothing is lost.
    if request.endpoint != "info.contact":
        return handle_rate_limited(error)

    seconds = seconds_until_retry()
    values, _ = _validate_contact(request.form)
    response, status = _render_contact(
        values,
        notice=f"You've sent several messages recently. Please wait {describe_wait(seconds)} and try again.",
        status=429,
    )
    return response, status, ({"Retry-After": str(seconds)} if seconds else {})


@info_bp.route("/privacy")
def privacy():
    return render_template("privacy.html", active_page="privacy")
