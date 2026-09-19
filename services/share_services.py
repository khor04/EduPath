import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from flask import current_app

from extensions import db
from models.report_share import ReportShare

SHARE_LIFETIME = timedelta(days=7)


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _derive_token(salt):
    """
    Deterministic: the same salt (and SECRET_KEY) always gives the same
    token, which is what lets the student's link be shown again without
    the token ever being stored.
    """
    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY must be set to create report-share links.")

    digest = hmac.new(secret.encode("utf-8"), salt.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_share(user_id):
    """
    Returns (share, token).

    A student has at most one live link: creating a new one deletes the
    old one. That keeps this feature free of any link-management UI,
    while still giving a student a way to kill a link they sent to the
    wrong person -- just create a new one.
    """
    ReportShare.query.filter_by(user_id=user_id).delete(synchronize_session=False)

    salt = secrets.token_urlsafe(16)
    token = _derive_token(salt)
    share = ReportShare(
        user_id=user_id,
        salt=salt,
        token_hash=_hash_token(token),
        expires_at=datetime.utcnow() + SHARE_LIFETIME,
    )
    db.session.add(share)
    db.session.commit()
    return share, token


def get_current_link(user_id):
    """
    The student's live link as (share, token), or None if they have
    none (never created, or expired).

    The re-derived token is checked against the stored hash before it's
    returned. If it doesn't match -- SECRET_KEY was changed since the
    link was made, or the row predates the salt column -- the link can't
    be shown again and this returns None, so the student is offered a
    new one instead of being handed a URL that doesn't work. (An
    advisor who already has the old URL is unaffected: that's validated
    by find_active_share, from the hash alone.)
    """
    share = (
        ReportShare.query
        .filter(ReportShare.user_id == user_id, ReportShare.expires_at > datetime.utcnow())
        .order_by(ReportShare.created_at.desc())
        .first()
    )
    if share is None or not share.salt:
        return None

    token = _derive_token(share.salt)
    if not hmac.compare_digest(_hash_token(token), share.token_hash):
        return None
    return share, token


def find_active_share(token):
    """The share for this token, or None if unknown or expired."""
    share = ReportShare.query.filter_by(token_hash=_hash_token(token)).first()
    if share is None or share.expires_at <= datetime.utcnow():
        return None
    return share


def delete_user_shares(user_id):
    ReportShare.query.filter_by(user_id=user_id).delete(synchronize_session=False)
