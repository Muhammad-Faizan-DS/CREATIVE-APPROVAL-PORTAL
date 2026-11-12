"""Submitting a version for review and recording the one decision."""

from flask import Blueprint, abort, flash, redirect, render_template, request
from flask import url_for
from sqlalchemy.exc import IntegrityError

from ..access import (
    campaign_of_round,
    campaign_of_version,
    can_approve_for,
    can_produce,
    in_client,
    is_client,
    is_manager,
    require_view,
)
from ..extensions import db
from ..models import CreativeVersion, ReviewAssignment, ReviewDecision, ReviewRound
from ..security import current_user, login_required
from ..workflow import DECISION_OUTCOMES, is_draft

bp = Blueprint("reviews", __name__)


@bp.post("/versions/<int:version_id>/submit")
@login_required
def submit_version(version_id):
    """Open the review round and assign the chosen client reviewer."""
    version = db.get_or_404(CreativeVersion, version_id)
    user = current_user()
    campaign = campaign_of_version(version)
    require_view(user, campaign)
    if not can_produce(user, campaign):
        abort(403)

    back = url_for("creatives.version_detail", version_id=version.id)
    if not is_draft(version):
        flash("This version has already been submitted.", "error")
        return redirect(back, code=303)
    if version.creative.deliverable.brief.status != "submitted":
        flash("The brief must be submitted before a review can start.", "error")
        return redirect(back, code=303)
    if not version.previews:
        flash("Upload a preview image before submitting for review.", "error")
        return redirect(back, code=303)

    reviewer_id = request.form.get("reviewer_id", type=int)
    members = {m.user_id for m in campaign.brand.client.memberships}
    if reviewer_id not in members:
        flash("Choose a reviewer from the client organisation.", "error")
        return redirect(back, code=303)

    review_round = ReviewRound(creative_version_id=version.id, opened_by=user.id)
    db.session.add(review_round)
    db.session.flush()
    db.session.add(
        ReviewAssignment(
            review_round_id=review_round.id,
            reviewer_id=reviewer_id,
            can_decide=True,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("This version is already in review.", "error")
        return redirect(back, code=303)

    flash("Version submitted for review.", "success")
    return redirect(url_for("reviews.detail", round_id=review_round.id), code=303)


@bp.get("/reviews/<int:round_id>")
@login_required
def detail(round_id):
    review_round = db.get_or_404(ReviewRound, round_id)
    user = current_user()
    campaign = campaign_of_round(review_round)
    require_view(user, campaign)
    return render_template(
        "reviews/detail.html",
        review_round=review_round,
        can_decide=_may_decide(user, review_round),
        outcomes=DECISION_OUTCOMES,
    )


def _may_decide(user, review_round):
    """Assignment, client membership, can_approve and can_decide all count."""
    if review_round.decision is not None:
        return False
    campaign = campaign_of_round(review_round)
    client_id = campaign.brand.client_id
    if not is_client(user) or not in_client(user, client_id):
        return False
    if not can_approve_for(user, client_id):
        return False
    return any(
        a.reviewer_id == user.id and a.can_decide
        for a in review_round.assignments
    )


@bp.post("/reviews/<int:round_id>/decision")
@login_required
def decide(round_id):
    """Record exactly one decision for the round."""
    review_round = db.get_or_404(ReviewRound, round_id)
    user = current_user()
    require_view(user, campaign_of_round(review_round))
    back = url_for("reviews.detail", round_id=review_round.id)

    if not _may_decide(user, review_round):
        abort(403)

    outcome = request.form.get("outcome", "")
    note = request.form.get("note", "").strip()
    if outcome not in DECISION_OUTCOMES:
        flash("Choose approve or request changes.", "error")
        return redirect(back, code=303)
    if outcome == "changes_requested" and not note:
        flash("Explain what should change before requesting changes.", "error")
        return redirect(back, code=303)

    db.session.add(
        ReviewDecision(
            review_round_id=review_round.id,
            decided_by=user.id,
            outcome=outcome,
            note=note or None,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("This round already has a decision.", "error")
        return redirect(back, code=303)

    flash("Decision recorded.", "success")
    return redirect(back, code=303)


@bp.post("/reviews/<int:round_id>/decision/withdraw")
@login_required
def withdraw_decision(round_id):
    """Undo a decision only while nothing depends on it."""
    review_round = db.get_or_404(ReviewRound, round_id)
    user = current_user()
    require_view(user, campaign_of_round(review_round))
    back = url_for("reviews.detail", round_id=review_round.id)
    decision = review_round.decision
    if decision is None:
        flash("There is no decision to withdraw.", "error")
        return redirect(back, code=303)
    if not is_manager(user) and decision.decided_by != user.id:
        abort(403)

    version = review_round.version
    later_versions = [
        v for v in version.creative.versions
        if v.version_number > version.version_number
    ]
    if later_versions:
        flash("A later version exists. The decision stays.", "error")
        return redirect(back, code=303)
    if any(cr.resolved_by_version_id for cr in review_round.change_requests):
        flash("Resolved change requests depend on this decision.", "error")
        return redirect(back, code=303)
    if version.delivery_items:
        flash("This version is part of a delivery batch.", "error")
        return redirect(back, code=303)

    db.session.delete(decision)
    db.session.commit()
    flash("Decision withdrawn.", "success")
    return redirect(back, code=303)


@bp.post("/reviews/<int:round_id>/delete")
@login_required
def delete_round(round_id):
    """A manager may remove a round that never started."""
    review_round = db.get_or_404(ReviewRound, round_id)
    user = current_user()
    require_view(user, campaign_of_round(review_round))
    if not is_manager(user):
        abort(403)
    version_id = review_round.creative_version_id
    back = url_for("creatives.version_detail", version_id=version_id)
    if (
        review_round.decision
        or review_round.comments
        or review_round.change_requests
        or review_round.assignments
    ):
        flash("Remove the reviewers and feedback before deleting the round.",
              "error")
        return redirect(url_for("reviews.detail", round_id=round_id), code=303)
    db.session.delete(review_round)
    db.session.commit()
    flash("Review round removed. The version is a draft again.", "success")
    return redirect(back, code=303)
