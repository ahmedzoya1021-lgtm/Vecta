"""
Signup, login, and logout routes.

Flask-Login handles remembering "who is logged in" across requests using a
secure cookie. We never store plain-text passwords — see User.set_password
in models.py, which hashes them.
"""
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from models import User, db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("signup.html", error="Email and password are required.")

    if User.query.filter_by(email=email).first():
        return render_template("signup.html", error="An account with that email already exists.")

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return redirect(url_for("index"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return render_template("login.html", error="Invalid email or password.")

    login_user(user)
    return redirect(url_for("index"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
