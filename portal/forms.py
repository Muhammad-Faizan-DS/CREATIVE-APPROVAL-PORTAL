"""A small field description layer shared by every record form.

Each screen describes its fields once. The form helper then reads the POST
body, validates every value on the server, and reports one message per
field so the template can redisplay what the person typed.
"""

import re
from datetime import date

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Field:
    """One editable column on a record form."""

    def __init__(
        self,
        name,
        label,
        kind="text",
        required=True,
        maxlength=None,
        choices=None,
        values=None,
        min_value=None,
        max_value=None,
        create_only=False,
        help_text=None,
    ):
        self.name = name
        self.label = label
        self.kind = kind
        self.required = required
        self.maxlength = maxlength
        self.choices = choices
        self.values = values
        self.min_value = min_value
        self.max_value = max_value
        self.create_only = create_only
        self.help_text = help_text

    def options(self, parent=None, obj=None):
        """Return the (value, label) pairs a select field may hold."""
        if self.kind == "enum":
            return [(value, value.replace("_", " ")) for value in self.values]
        if self.choices is None:
            return []
        return list(self.choices(parent, obj))

    def applies(self, obj):
        """Create-only fields, such as a parent choice, are fixed on edit."""
        return not (self.create_only and obj is not None and obj.id is not None)


def parse_field(field, form, parent, obj):
    """Return (value, error) for one submitted field."""
    if field.kind == "bool":
        return field.name in form, None

    raw = form.get(field.name, "")
    raw = raw.strip() if isinstance(raw, str) else raw

    if raw == "":
        if field.required:
            return None, f"Enter {field.label.lower()}."
        return None, None

    if field.kind in ("text", "textarea", "email", "url"):
        if field.maxlength and len(raw) > field.maxlength:
            return None, f"Use at most {field.maxlength} characters."
        if field.kind == "email":
            raw = raw.casefold()
            if not EMAIL_PATTERN.match(raw):
                return None, "Enter a valid email address."
        if field.kind == "url" and not raw.startswith(("http://", "https://")):
            return None, "Enter a link that starts with http:// or https://."
        return raw, None

    if field.kind == "int":
        try:
            value = int(raw)
        except ValueError:
            return None, f"Enter {field.label.lower()} as a whole number."
        if field.min_value is not None and value < field.min_value:
            return None, f"Enter {field.min_value} or more."
        if field.max_value is not None and value > field.max_value:
            return None, f"Enter {field.max_value} or less."
        return value, None

    if field.kind == "date":
        try:
            return date.fromisoformat(raw), None
        except ValueError:
            return None, "Enter the date as YYYY-MM-DD."

    if field.kind == "enum":
        if raw not in field.values:
            return None, "Choose one of the listed values."
        return raw, None

    if field.kind == "select":
        try:
            value = int(raw)
        except ValueError:
            return None, f"Choose an existing {field.label.lower()}."
        allowed = {option[0] for option in field.options(parent, obj)}
        if value not in allowed:
            return None, f"Choose an existing {field.label.lower()}."
        return value, None

    raise ValueError(f"Unknown field kind {field.kind!r}")


def read_form(fields, form, parent=None, obj=None):
    """Validate every applicable field. Return (values, errors)."""
    values, errors = {}, {}
    for field in fields:
        if not field.applies(obj):
            continue
        value, error = parse_field(field, form, parent, obj)
        if error:
            errors[field.name] = error
        else:
            values[field.name] = value
    return values, errors


def display_value(field, obj, submitted=None):
    """The string a form input should show."""
    if submitted is not None and field.name in submitted:
        return submitted[field.name]
    if obj is None:
        return "" if field.kind != "bool" else False
    value = getattr(obj, field.name, None)
    if value is None:
        return "" if field.kind != "bool" else False
    if field.kind == "bool":
        return bool(value)
    if field.kind == "date":
        return value.isoformat()
    return value


def form_state(fields, obj, form=None):
    """Build the values the template renders, preferring submitted text."""
    submitted = None
    if form is not None:
        submitted = {}
        for field in fields:
            if field.kind == "bool":
                submitted[field.name] = field.name in form
            elif field.name in form:
                submitted[field.name] = form.get(field.name, "").strip()
    return {
        field.name: display_value(field, obj, submitted) for field in fields
    }
