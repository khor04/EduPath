from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from markupsafe import Markup
from extensions import db,mail
from models.users import User
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
import re

auth_bp = Blueprint("auth", __name__)

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
      
def send_verification_email(user):
    token = generate_token(user.user_id)

    verify_url = url_for("auth.verify_email", token=token, _external=True)

    msg = Message(
    subject="Verify Your EduPath Account",
    recipients=[user.email_pending or user.email]
    )

    msg.body = f"""
Hi {user.username},


Please click the link below to verify your email:

{verify_url}

This link will expire in 1 hour.
If you did NOT request this change, ignore this email.

Regards,
EduPath System
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


@auth_bp.route("/signup", methods=["GET", "POST"])
def register():
    
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        department = request.form.get("department")
        batch = request.form.get("batch")

        password_pattern = r'^(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\'":\\|,.<>/?]).{8,}$'

        if not re.match(password_pattern, password):
            flash(
                "Password must be at least 8 characters long and contain at least 1 digit and 1 special character.",
                "error"
            )
            return redirect(url_for("auth.register"))
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash(
                Markup('Email already registered. <a href="' + url_for("auth.login") + '">Login here</a>'),
                "error"
            )
            return redirect(url_for("auth.register"))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            department=department,
            batch=batch
        )

        db.session.add(new_user)
        db.session.commit()
        send_verification_email(new_user)

        flash("Account created. Please verify your email before login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("signup.html")


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    user_id = verify_token(token)

    if not user_id:
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("auth.register"))

    
    #case 1: email change
    if user.email_pending:
    
        user.email = user.email_pending
        user.email_pending = None

        db.session.commit()

        flash("Email updated and verified successfully!", "success")
        return redirect(url_for("auth.login"))

    #case 2: signup / normal verify
    if user.is_verified:
        flash("Email verified successfully!", "success")
        return redirect(url_for("auth.login"))
    
    user.is_verified = True
        
    db.session.commit()

    flash("Email verified successfully!", "success")
    return redirect(url_for("auth.login"))
    

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            if not user.is_verified:
                flash("Please verify your email before logging in.", "error")
                return redirect(url_for("auth.login"))

            login_user(user)
            return redirect(url_for("dashboard.dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    return render_template("login.html")

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()

        if user:
            send_reset_email(user)

            return redirect(url_for("auth.forgot_password", modal="email_sent"))

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