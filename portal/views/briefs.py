"""Briefs and the production tasks created from them."""

from flask import Blueprint, abort, flash, redirect, render_template, url_for

from ..access import campaign_of_brief, campaign_of_task, can_brief, require_view
from ..extensions import db
from ..models import Brief, Task
from ..security import current_user, login_required

bp = Blueprint("briefs", __name__)


@bp.get("/briefs/<int:brief_id>")
@login_required
def detail(brief_id):
    brief = db.get_or_404(Brief, brief_id)
    require_view(current_user(), campaign_of_brief(brief))
    return render_template("briefs/detail.html", brief=brief)


@bp.post("/briefs/<int:brief_id>/submit")
@login_required
def submit(brief_id):
    """Check the brief is complete, then move draft to submitted."""
    brief = db.get_or_404(Brief, brief_id)
    user = current_user()
    campaign = campaign_of_brief(brief)
    require_view(user, campaign)
    if not can_brief(user, campaign):
        abort(403)

    back = url_for("briefs.detail", brief_id=brief.id)
    if brief.status != "draft":
        flash("This brief has already been submitted.", "error")
        return redirect(back, code=303)
    if not brief.deliverables:
        flash("Add at least one deliverable before submitting.", "error")
        return redirect(back, code=303)
    if not brief.requirements:
        flash("Add at least one requirement before submitting.", "error")
        return redirect(back, code=303)
    if any(item.quantity < 1 for item in brief.deliverables):
        flash("Every deliverable needs a quantity of 1 or more.", "error")
        return redirect(back, code=303)

    brief.status = "submitted"
    db.session.commit()
    flash("Brief submitted. The team can start work.", "success")
    return redirect(back, code=303)


@bp.post("/briefs/<int:brief_id>/reopen")
@login_required
def reopen(brief_id):
    """A manager can reopen a brief that has no creatives yet."""
    brief = db.get_or_404(Brief, brief_id)
    user = current_user()
    if user.role.code != "manager":
        abort(403)
    back = url_for("briefs.detail", brief_id=brief.id)
    if any(item.creatives for item in brief.deliverables):
        flash("Work has started. This brief stays submitted.", "error")
        return redirect(back, code=303)
    brief.status = "draft"
    db.session.commit()
    flash("Brief reopened as a draft.", "success")
    return redirect(back, code=303)


@bp.get("/tasks/<int:task_id>")
@login_required
def task_detail(task_id):
    task = db.get_or_404(Task, task_id)
    require_view(current_user(), campaign_of_task(task))
    return render_template("tasks/detail.html", task=task)
