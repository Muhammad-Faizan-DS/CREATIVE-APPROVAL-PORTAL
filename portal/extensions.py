"""Shared extension objects.

Keeping the SQLAlchemy object in its own module lets the models and the
application factory import it without creating a circular import.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
