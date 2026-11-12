"""Entry point for a serverless host such as Vercel.

The platform imports `app` from this module and serves it as a WSGI
application, with the request path intact. Only the scratch directory is
writable there, so the portal keeps its database and uploads in /tmp and
seeds the demo data on every cold start. Running locally is unaffected:
use `python -m flask --app portal run` as the README describes.
"""

import os

os.environ.setdefault("PORTAL_DATA_DIR", "/tmp/portal")
os.environ.setdefault("PORTAL_DEMO_SEED", "1")

from portal import create_app  # noqa: E402  (after the defaults are set)

app = create_app()
