from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from markupsafe import Markup
from extensions import db, mail, limiter
from models.users import User
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
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
            user.email = user.email_pending
            user.email_pending = None
            success_msg = "Email updated and verified successfully! Please log in."
        else:
            user.is_verified = True
            success_msg = "Email verified successfully! You can now log in."

        user.verification_code_hash = None
        user.verification_expires_at = None
        user.verification_attempts = 0
        db.session.commit()

        flash(success_msg, "success")
        return redirect(url_for("auth.login"))

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