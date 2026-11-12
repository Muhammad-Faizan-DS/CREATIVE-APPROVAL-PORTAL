"""Entry point for a serverless host such as Vercel.

The platform imports `app` from this module and calls it as a WSGI
application. Only the scratch directory is writable there, so the portal
keeps its database and uploads in /tmp and restores the packaged demo
data on every cold start.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("PORTAL_DATA_DIR", "/tmp/portal")
os.environ.setdefault("PORTAL_DEMO_SEED", "1")

from portal import create_app  # noqa: E402  (after sys.path is set)

app = create_app()
