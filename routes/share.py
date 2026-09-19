import re
from datetime import date

from flask import Blueprint, Response, jsonify, make_response, render_template, url_for
from flask_login import current_user, login_required

from models.semester import Semester
from models.transcript import Transcript
from models.users import User
from services.report_services import build_report_context, html_to_pdf_bytes
from services.share_services import create_share, find_active_share, get_current_link

share_bp = Blueprint("share", __name__)


def _private(response):
    """
    The link is a bearer secret sitting in the URL: keep it out of
    search indexes, shared caches and Referer headers.
    """
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _invalid_link_response():
    return _private(make_response(render_template("shared_report_invalid.html"), 404))


def _link_payload(share, token):
    # A path, not a full URL: the browser knows the real public origin
    # (behind a proxy, url_for(_external=True) can come out as http://).
    return {
        "success": True,
        "has_link": True,
        "path": url_for("share.shared_report", token=token),
        "expires_at": share.expires_at.isoformat() + "Z",
    }


@share_bp.route("/dashboard/report/share", methods=["GET"])
@login_required
def current_report_share():
    """The student's live link, if they have one -- so closing the dialog
    doesn't lose it."""
    current = get_current_link(current_user.user_id)
    if current is None:
        return _private(jsonify({"success": True, "has_link": False}))
    return _private(jsonify(_link_payload(*current)))


@share_bp.route("/dashboard/report/share", methods=["POST"])
@login_required
def create_report_share():
    has_grades = (
        Semester.query
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == current_user.user_id, Semester.semester_gpa != None)
        .first()
    )
    if not has_grades:
        return jsonify({
            "success": False,
            "message": "Upload your transcript first -- there is no report to share yet.",
        }), 400

    share, token = create_share(current_user.user_id)
    return _private(jsonify(_link_payload(share, token)))


@share_bp.route("/shared/<token>")
def shared_report(token):
    share = find_active_share(token)
    if share is None:
        return _invalid_link_response()

    context = build_report_context(share.user_id)
    return _private(make_response(render_template(
        "report.html",
        is_pdf=False,
        shared=True,
        shared_expires_on=share.expires_at.strftime("%d %b %Y, %H:%M UTC"),
        download_url=url_for("share.shared_report_pdf", token=token),
        **context,
    )))


@share_bp.route("/shared/<token>/pdf")
def shared_report_pdf(token):
    share = find_active_share(token)
    if share is None:
        return _invalid_link_response()

    context = build_report_context(share.user_id)
    if not context.get("has_transcript"):
        return _invalid_link_response()

    html = render_template("report.html", is_pdf=True, **context)
    pdf_bytes = html_to_pdf_bytes(html)

    user = User.query.get(share.user_id)
    safe_username = re.sub(r"[^A-Za-z0-9_-]", "_", user.username)
    filename = f"academic_report_{safe_username}_{date.today().isoformat()}.pdf"

    return _private(Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    ))
