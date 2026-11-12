"""Scope rules: which campaign records a signed-in account may touch.

A manager sees everything. A designer sees the campaigns of the teams they
belong to. A client reviewer sees the campaigns of their own organisation.
"""

from flask import abort


def is_manager(user):
    return user is not None and user.role.code == "manager"


def is_designer(user):
    return user is not None and user.role.code == "designer"


def is_client(user):
    return user is not None and user.role.code == "client"


def in_team(user, team_id):
    return user is not None and any(
        m.team_id == team_id for m in user.team_memberships
    )


def in_client(user, client_id):
    return user is not None and any(
        m.client_id == client_id for m in user.client_memberships
    )


def can_approve_for(user, client_id):
    return user is not None and any(
        m.client_id == client_id and m.can_approve
        for m in user.client_memberships
    )


# --- walking back up to the owning campaign -------------------------------

def campaign_of_brief(brief):
    return brief.campaign


def campaign_of_deliverable(deliverable):
    return deliverable.brief.campaign


def campaign_of_creative(creative):
    return creative.deliverable.brief.campaign


def campaign_of_version(version):
    return campaign_of_creative(version.creative)


def campaign_of_round(review_round):
    return campaign_of_version(review_round.version)


def campaign_of_task(task):
    return task.brief.campaign


# --- the questions the views ask ------------------------------------------

def can_view_campaign(user, campaign):
    """Managers, the assigned team and the owning client can read it."""
    if campaign is None:
        return False
    if is_manager(user):
        return True
    if is_designer(user):
        return in_team(user, campaign.team_id)
    if is_client(user):
        return in_client(user, campaign.brand.client_id)
    return False


def can_produce(user, campaign):
    """Managers and the campaign's designers may change production records."""
    return is_manager(user) or (
        is_designer(user) and in_team(user, campaign.team_id)
    )


def can_brief(user, campaign):
    """Managers and the campaign's client may change brief records."""
    return is_manager(user) or (
        is_client(user) and in_client(user, campaign.brand.client_id)
    )


def require_view(user, campaign):
    """404 for anything outside the account's scope."""
    if not can_view_campaign(user, campaign):
        abort(404)
    return campaign
