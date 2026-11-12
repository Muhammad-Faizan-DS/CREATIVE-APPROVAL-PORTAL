"""Derived status for a creative version, and the actions it allows."""

DRAFT = "Draft"
IN_REVIEW = "In review"
CHANGES_REQUESTED = "Changes requested"
APPROVED = "Approved"
DELIVERED = "Delivered"

BRIEF_STATUSES = ("draft", "submitted")
TASK_STATUSES = ("todo", "doing", "done")
CAMPAIGN_STATUSES = ("planned", "active", "closed")
DECISION_OUTCOMES = ("changes_requested", "approved")
FILE_KINDS = ("preview", "export")


def version_status(version):
    """Check a sent delivery first, then the round and its decision."""
    if any(item.batch.is_sent for item in version.delivery_items):
        return DELIVERED
    review_round = version.review_round
    if review_round is None:
        return DRAFT
    decision = review_round.decision
    if decision is None:
        return IN_REVIEW
    if decision.outcome == "approved":
        return APPROVED
    return CHANGES_REQUESTED


def is_draft(version):
    return version_status(version) == DRAFT


def is_approved(version):
    """Approved versions may be added to a delivery batch."""
    return version_status(version) in (APPROVED, DELIVERED)


def creative_status(creative):
    latest = creative.latest_version
    return version_status(latest) if latest else "No version yet"


def next_version_number(creative):
    """Version numbers start at 1 and never reuse a number."""
    if not creative.versions:
        return 1
    return max(v.version_number for v in creative.versions) + 1


def can_start_next_version(creative):
    """A new draft is allowed only after changes were requested."""
    latest = creative.latest_version
    if latest is None:
        return True
    return version_status(latest) == CHANGES_REQUESTED
