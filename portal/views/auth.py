"""Sign in and sign out."""

from flask import Blueprint, flash, redirect, render_template
from flask import request, session, url_for
from werkzeug.security import check_password_hash

from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "").strip().casefold()
    password = request.form.get("password", "")
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if not user or not user.is_active or not check_password_hash(
        user.password_hash, password
    ):
        return render_template(
            "auth/login.html", error="Check your email and password."
        ), 400

    session.clear()
    session["user_id"] = user.id
    return redirect(url_for("dashboard.home"), code=303)


@bp.post("/logout")
def logout():
    session.clear()
    flash("You signed out.", "success")
    return redirect(url_for("auth.login"), code=303)
