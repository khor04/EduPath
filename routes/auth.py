from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from markupsafe import Markup
from extensions import db, mail, limiter
from models.users import User
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from utils.validators import is_valid_password, PASSWORD_REQUIREMENT_MESSAGE, is_um_email, UM_EMAIL_DOMAIN
import secrets
from datetime import datetime, timedelta

auth_bp = Blueprint("auth", __name__)

VERIFICATION_CODE_TTL = timedelta(hours=1)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_VERIFICATION_ATTEMPTS = 5

def generate_token(user_id):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(user_id, salt='email-confirm')

def verify_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    try:
        user_id = serializer.loads(token, salt="email-confirm", max_age=expiration)
        return user_id
    except:
        return None

def generate_verification_code():
    return f"{secrets.randbelow(1000000):06d}"

def resend_on_cooldown(user):
    if not user.verification_expires_at:
        return False

    sent_at = user.verification_expires_at - VERIFICATION_CODE_TTL
    return datetime.utcnow() < sent_at + RESEND_COOLDOWN

def issue_verification_code(user):
    code = generate_verification_code()

    user.verification_code_hash = generate_password_hash(code)
    user.verification_expires_at = datetime.utcnow() + VERIFICATION_CODE_TTL
    user.verification_attempts = 0

    db.session.commit()

    send_verification_email(user, code)

    return code

def send_verification_email(user, code):
    recipient = user.email_pending or user.email

    msg = Message(
        subject="Verify Your EduPath Account",
        recipients=[recipient]
    )

    msg.body = f"""Please verify your identity, {user.username}

Here is your verification code:

{code}

This code is valid for 1 hour and can only be used once.

Please don't share this code with anyone: we'll never ask for it on the phone or via email.

If you didn't request this, you can safely ignore this email. No account will be verified without this code.

Thanks,
EduPath team
"""

    mail.send(msg)

#forgot password
def send_reset_email(user):
    
    token = generate_token(user.user_id)

    reset_url = url_for(
        'auth.reset_password',
        token=token,
        _external=True
    )

    msg = Message(
        subject="EduPath Password Reset",
        recipients=[user.email]
    )

    msg.body = f"""
Hi {user.username},

Click the link below to reset your password:

{reset_url}

This link will expire in 1 hour.

Regards,
EduPath System
"""

    mail.send(msg)

@auth_bp.route("/check-availability", methods=["POST"])
@limiter.limit("15 per minute")
def check_availability():
    try:
        data = request.get_json(silent=True) or {}

        email = (data.get("email") or "").strip()
        username = (data.get("username") or "").strip()

        email_taken = False
        username_taken = False

        if email:
            email_taken = (
                User.query.filter(User.email == email).first() is not None
            )

        if username:
            username_taken = (
                User.query.filter(User.username == username).first() is not None
            )

        return jsonify({
            "email_taken": email_taken,
            "username_taken": username_taken
        })

    except Exception as e:
        print("check_availability error:", e)  # IMPORTANT for debugging
        return jsonify({
            "email_taken": False,
            "username_taken": False,
            "error": "server error"
        }), 200
    
    
@auth_bp.route("/signup", methods=["GET", "POST"])
def register():
    
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        faculty = request.form.get("faculty")
        programme = request.form.get("programme")
        batch = request.form.get("batch")

        if not faculty:
            flash("Please select a faculty.", "error")
            return redirect(url_for("auth.register"))

        if not programme:
            flash("Please select a programme.", "error")
            return redirect(url_for("auth.register"))

        if not batch:
            flash("Please select a batch.", "error")
            return redirect(url_for("auth.register"))

        if not is_um_email(email):
            flash(f"Only @{UM_EMAIL_DOMAIN} email addresses can register.", "error")
            return redirect(url_for("auth.register"))

        if not is_valid_password(password):
            flash(PASSWORD_REQUIREMENT_MESSAGE, "error")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            if existing_user.is_verified:
                flash(
                    Markup(
                        'Email already registered. <a href="' + url_for("auth.login") + '">Login here</a> '
                        'or <a href="' + url_for("auth.forgot_password") + '">reset your password</a>.'
                    ),
                    "error"
                )
                return redirect(url_for("auth.register"))

            expired = (
                not existing_user.verification_expires_at
                or datetime.utcnow() > existing_user.verification_expires_at
            )

            if expired:
                db.session.delete(existing_user)
                db.session.commit()
            else:
                if resend_on_cooldown(existing_user):
                    flash("An account with this email is already pending verification. Check your email for the code we already sent.", "success")
                else:
                    issue_verification_code(existing_user)
                    flash("An account with this email is already pending verification. We've sent you a new code.", "success")

                return redirect(url_for("auth.verify_code_page", email=email))

        existing_username = User.query.filter_by(username=username).first()

        if existing_username:
            flash("Username already exists.", "error")
            return redirect(url_for("auth.register"))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            faculty=faculty,
            programme=programme,
            batch=batch
        )

        db.session.add(new_user)
        db.session.commit()
        issue_verification_code(new_user)

        flash("Account created. Please check your email for a verification code.", "success")
        return redirect(url_for("auth.verify_code_page", email=email))

    return render_template("signup.html")


@auth_bp.route("/verify-code", methods=["GET", "POST"])
@limiter.limit("20 per minute", methods=["POST"])
def verify_code_page():

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        code = (request.form.get("code") or "").strip()

        # When the browser is still logged in (the normal case now that an
        # email change no longer forces a logout), resolve the pending
        # verification from the session itself rather than this global
        # email/email_pending match. Without this, once someone else's
        # verified `email` legitimately equals what's still sitting in
        # this user's `email_pending` (e.g. they lost that email-uniqueness
        # race and haven't been cleaned up by a request yet), the OR match
        # below could resolve to the wrong row entirely.
        if current_user.is_authenticated and current_user.email_pending == email:
            user = current_user
        else:
            user = User.query.filter(
                (User.email == email) | (User.email_pending == email)
            ).first()

        if not user or not user.verification_code_hash or not user.verification_expires_at:
            flash("Invalid verification session. Please request a new code.", "error")
            return redirect(url_for("auth.verify_code_page", email=email))

        if datetime.utcnow() > user.verification_expires_at:
            flash("This code has expired. Please request a new one.", "error")
            return redirect(url_for("auth.verify_code_page", email=email))

        if not check_password_hash(user.verification_code_hash, code):
            user.verification_attempts += 1

            if user.verification_attempts >= MAX_VERIFICATION_ATTEMPTS:
                user.verification_code_hash = None
                user.verification_expires_at = None
                user.verification_attempts = 0
                db.session.commit()

                flash("Too many incorrect attempts. Please request a new code.", "error")
                return redirect(url_for("auth.verify_code_page", email=email))

            db.session.commit()

            remaining = MAX_VERIFICATION_ATTEMPTS - user.verification_attempts
            flash(f"Incorrect code. {remaining} attempt(s) remaining.", "error")
            return redirect(url_for("auth.verify_code_page", email=email))

        if user.email_pending:
            # An email change no longer logs the user out at request time
            # (routes/profile.py) -- the old email stays the login email
            # until this verification succeeds, and the session survives
            # the whole way through. So on success (or a rejection here),
            # send them back to where they still are (profile) instead of
            # a login page they don't need, unless the session genuinely
            # isn't theirs (e.g. they verify from a different browser/tab
            # than the one that requested the change).
            still_logged_in_as_user = (
                current_user.is_authenticated and current_user.user_id == user.user_id
            )
            redirect_target = "profile.profile" if still_logged_in_as_user else "auth.login"

            # Re-checked here, not just at request time (routes/profile.py)
            # -- that check can't close the window between two people
            # racing to claim the same email. This is the moment the
            # change actually takes effect, so it's checked again right
            # before it does.
            conflict = User.query.filter(
                User.user_id != user.user_id,
                (User.email == user.email_pending) | (User.email_pending == user.email_pending),
            ).first()

            if conflict:
                user.email_pending = None
                user.verification_code_hash = None
                user.verification_expires_at = None
                user.verification_attempts = 0
                db.session.commit()

                flash(
                    "This email address is no longer available. Please request another email address.",
                    "error"
                )
                return redirect(url_for(redirect_target))

            user.email = user.email_pending
            user.email_pending = None
            success_msg = "Email updated successfully!" if still_logged_in_as_user else "Email updated and verified successfully! Please log in."
        else:
            user.is_verified = True
            success_msg = "Email verified successfully! You can now log in."
            redirect_target = "auth.login"

        user.verification_code_hash = None
        user.verification_expires_at = None
        user.verification_attempts = 0

        try:
            db.session.commit()
        except IntegrityError:
            # Backstop for the exact race the check above narrows but
            # can't fully close (two commits landing at the same instant)
            # -- the database's own unique=True constraint on User.email
            # is the last line of defense, and this turns it into a
            # clean message instead of a raw 500.
            db.session.rollback()
            flash(
                "This email address is no longer available. Please request another email address.",
                "error"
            )
            return redirect(url_for(redirect_target))

        flash(success_msg, "success")
        return redirect(url_for(redirect_target))

    email = request.args.get("email", "")
    return render_template("verify_code.html", email=email)


@auth_bp.route("/resend-code", methods=["POST"])
@limiter.limit("10 per minute")
def resend_code():
    email = (request.form.get("email") or "").strip()

    user = User.query.filter(
        (User.email == email) | (User.email_pending == email)
    ).first()

    if not user or (user.is_verified and not user.email_pending):
        flash("No pending verification found for this email.", "error")
        return redirect(url_for("auth.verify_code_page", email=email))

    if resend_on_cooldown(user):
        flash("Please wait a moment before requesting another code.", "error")
        return redirect(url_for("auth.verify_code_page", email=email))

    issue_verification_code(user)

    flash("A new verification code has been sent.", "success")
    return redirect(url_for("auth.verify_code_page", email=email))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            if not user.is_verified:
                flash(
                    Markup(
                        'Please verify your email before logging in. '
                        '<a href="' + url_for("auth.verify_code_page", email=user.email) + '">Enter verification code</a>'
                    ),
                    "error"
                )
                return redirect(url_for("auth.login"))

            login_user(user)

            if user.is_admin:
                return redirect(url_for("admin.admin_stats"))

            return redirect(url_for("dashboard.dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    return render_template("login.html")

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()

        if user:
            send_reset_email(user)

            return redirect(url_for("auth.forgot_password", modal="email_sent", email=email))

        flash("Email not found.", "error")
        return redirect(url_for("auth.forgot_password"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    user_id = verify_token(token)

    if not user_id:
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.get(user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":

        password = request.form.get("password")

        if not is_valid_password(password):
            flash(PASSWORD_REQUIREMENT_MESSAGE, "error")
            return redirect(url_for("auth.reset_password", token=token))

        user.password = generate_password_hash(password)
        db.session.commit()

        flash("Password reset successfully.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))