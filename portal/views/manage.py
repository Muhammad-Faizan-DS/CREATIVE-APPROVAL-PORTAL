"""Shared create, read, update and delete screens for the registry tables.

Each resource in portal/resources.py gets the same four routes. The
resource decides which fields exist, who may use them, and where the
browser goes after a successful write.
"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import form_state, read_form
from ..resources import REGISTRY, record_url
from ..security import current_user, login_required

bp = Blueprint("manage", __name__, url_prefix="/manage")


def _resource(key):
    resource = REGISTRY.get(key)
    if resource is None:
        abort(404)
    return resource


def _parent_of(resource, obj):
    """Load the owning record of a child row."""
    if not resource.parent_attr:
        return None
    return db.session.get(resource.parent_model, getattr(obj, resource.parent_attr))


def _requested_parent(resource):
    """Load the parent named in the query string when creating a child."""
    if not resource.parent_attr:
        return None
    parent_id = request.args.get("parent_id", type=int)
    if parent_id is None:
        abort(400, "This record must be created from its own page.")
    parent = db.session.get(resource.parent_model, parent_id)
    if parent is None:
        abort(404)
    return parent


def _apply(resource, obj, parent, user):
    """Validate the POST body and save. Return an errors dict."""
    values, errors = read_form(resource.fields, request.form, parent, obj)
    if errors:
        return errors

    message = resource.validate(obj, values, parent, user)
    if message:
        return {"__all__": message}

    if parent is not None and obj.id is None:
        setattr(obj, resource.parent_attr, parent.id)

    message = resource.prepare(obj, values, parent, user)
    if message:
        return {"__all__": message}

    for name, value in values.items():
        setattr(obj, name, value)

    db.session.add(obj)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            "__all__": (
                f"That {resource.singular} clashes with an existing record. "
                "Check the values that must stay unique."
            )
        }
    return {}


def _render_form(resource, obj, parent, errors, submitted=None):
    status = 400 if errors else 200
    return render_template(
        "manage/form.html",
        resource=resource,
        record=obj,
        parent=parent,
        values=form_state(resource.fields, obj, submitted),
        errors=errors,
        back_url=resource.back_url(parent, obj if obj.id else None),
    ), status


@bp.get("/<key>")
@login_required
def index(key):
    """List a top-level table such as Users or Channels."""
    resource = _resource(key)
    if not resource.top_level:
        abort(404)
    user = current_user()
    if not resource.allow(user, "view", None, None):
        abort(403)
    rows = resource.rows()
    return render_template(
        "manage/list.html",
        resource=resource,
        rows=[
            {
                "obj": row,
                "cells": resource.cells(row),
                "detail_url": record_url(row) if resource.has_detail else None,
                "can_edit": resource.editable
                and resource.allow(user, "edit", None, row),
                "can_delete": resource.deletable
                and resource.allow(user, "delete", None, row),
                "edit_url": url_for("manage.edit", key=key, record_id=row.id),
                "delete_url": url_for("manage.delete", key=key, record_id=row.id),
            }
            for row in rows
        ],
        can_create=resource.creatable
        and resource.allow(user, "create", None, None),
    )


@bp.route("/<key>/new", methods=["GET", "POST"])
@login_required
def create(key):
    """Show the blank form, then validate and insert the record."""
    resource = _resource(key)
    if not resource.creatable:
        abort(404)
    user = current_user()
    parent = _requested_parent(resource)
    if not resource.allow(user, "create", parent, None):
        abort(403)

    obj = resource.model()
    if request.method == "GET":
        return _render_form(resource, obj, parent, {})

    errors = _apply(resource, obj, parent, user)
    if errors:
        return _render_form(resource, obj, parent, errors, request.form)
    flash(f"{resource.singular.capitalize()} saved.", "success")
    return redirect(resource.back_url(parent, obj), code=303)


@bp.route("/<key>/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def edit(key, record_id):
    """Load the record by its integer id, then validate and update it."""
    resource = _resource(key)
    if not resource.editable:
        abort(404)
    user = current_user()
    obj = db.get_or_404(resource.model, record_id)
    parent = _parent_of(resource, obj)
    if not resource.allow(user, "edit", parent, obj):
        abort(403)

    if request.method == "GET":
        return _render_form(resource, obj, parent, {})

    errors = _apply(resource, obj, parent, user)
    if errors:
        db.session.rollback()
        return _render_form(resource, obj, parent, errors, request.form)
    flash(f"{resource.singular.capitalize()} updated.", "success")
    return redirect(resource.back_url(parent, obj), code=303)


@bp.post("/<key>/<int:record_id>/delete")
@login_required
def delete(key, record_id):
    """Remove one record. A foreign key protects rows that have children."""
    resource = _resource(key)
    if not resource.deletable:
        abort(404)
    user = current_user()
    obj = db.get_or_404(resource.model, record_id)
    parent = _parent_of(resource, obj)
    if not resource.allow(user, "delete", parent, obj):
        abort(403)

    back = resource.back_url(parent, None)
    db.session.delete(obj)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            f"Remove the records that depend on this {resource.singular} first.",
            "error",
        )
        return redirect(back, code=303)
    flash(f"{resource.singular.capitalize()} deleted.", "success")
    return redirect(back, code=303)


def children(key, parent):
    """Template helper: the rows, links and permissions for a child list."""
    resource = REGISTRY[key]
    user = current_user()
    if not resource.allow(user, "view", parent, None):
        return None
    rows = []
    for row in resource.rows(parent):
        rows.append(
            {
                "obj": row,
                "cells": resource.cells(row),
                "detail_url": record_url(row) if resource.has_detail else None,
                "can_edit": resource.editable
                and resource.allow(user, "edit", parent, row),
                "can_delete": resource.deletable
                and resource.allow(user, "delete", parent, row),
                "edit_url": url_for("manage.edit", key=key, record_id=row.id),
                "delete_url": url_for(
                    "manage.delete", key=key, record_id=row.id
                ),
            }
        )
    return {
        "resource": resource,
        "rows": rows,
        "can_create": resource.creatable
        and resource.allow(user, "create", parent, None),
        "create_url": url_for("manage.create", key=key, parent_id=parent.id),
    }
