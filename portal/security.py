"""Session helpers, CSRF protection and role decorators."""

from functools import wraps
from secrets import compare_digest, token_urlsafe

from flask import abort, redirect, request, session, url_for

from .extensions import db
from .models import User


def csrf_token():
    """Return the session form token, creating it on first use."""
    if "csrf_token" not in session:
        session["csrf_token"] = token_urlsafe(32)
    return session["csrf_token"]


def protect_post():
    """Reject any POST that does not carry the session form token."""
    if request.method == "POST":
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not compare_digest(
            expected.encode("utf-8"), supplied.encode("utf-8")
        ):
            abort(400, "Missing or invalid form token. Reload the form.")


def current_user():
    """Return the signed-in, active user, or None for a guest."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user if user and user.is_active else None


def login_required(view):
    """Send guests to the sign-in page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def role_only(*codes):
    """Allow only the listed role codes; others get 403."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("auth.login"))
            if user.role.code not in codes:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


manager_only = role_only("manager")
