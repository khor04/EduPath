from functools import wraps

from flask import Blueprint, render_template, abort, redirect, url_for
from flask_login import login_required, current_user

from services.admin_services import (
    get_feedback_summary,
    get_feedback_overview,
    get_contact_messages,
    get_platform_stats,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/")
@admin_required
def admin_home():
    return redirect(url_for("admin.admin_stats"))


@admin_bp.route("/feedback")
@admin_required
def admin_feedback():
    feedback_summary = get_feedback_summary()
    return render_template(
        "admin/admin_feedback.html",
        active_admin_page="feedback",
        feedback_summary=feedback_summary,
        feedback_overview=get_feedback_overview(feedback_summary),
    )


@admin_bp.route("/contact")
@admin_required
def admin_contact():
    return render_template(
        "admin/admin_contact.html",
        active_admin_page="contact",
        messages=get_contact_messages(),
    )


@admin_bp.route("/stats")
@admin_required
def admin_stats():
    return render_template(
        "admin/admin_stats.html",
        active_admin_page="stats",
        stats=get_platform_stats(),
    )
