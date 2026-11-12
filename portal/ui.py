"""Small presentation helpers shared by the templates."""

BADGE_CLASSES = {
    # workflow states
    "draft": "neutral",
    "todo": "neutral",
    "planned": "neutral",
    "no version yet": "neutral",
    "submitted": "info",
    "doing": "info",
    "active": "info",
    "in review": "info",
    "changes requested": "warn",
    "approved": "ok",
    "delivered": "ok",
    "done": "ok",
    "closed": "neutral",
    "changes_requested": "warn",
    # yes / no columns
    "yes": "ok",
    "no": "neutral",
}


def badge_class(value):
    """Return the badge style for a status word, or None for plain text.

    Status is never shown by colour alone: the badge always carries the
    word itself and a dot, so it stays readable in both themes.
    """
    if value is None:
        return None
    return BADGE_CLASSES.get(str(value).strip().casefold())


def initials(name):
    """Up to two initials for the account avatar."""
    parts = [part for part in str(name or "").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "?"
