"""Gunicorn entry point: `gunicorn wsgi:app`.

Kept separate from app.py rather than adding a module-level `app = create_app()`
there, because several one-off scripts (scripts/create_admin.py,
scripts/migrate_*.py) already do `from app import create_app` and call it
themselves -- a module-level call in app.py would run create_app() a second
time (and its own DB setup/print) on every one of those imports.

It is also the one place that knows the app runs behind Render's proxy.
Render terminates HTTPS and forwards each request through exactly one proxy
hop, so without ProxyFix every request would appear to come from that proxy:
all visitors would share one rate-limit counter (one person could lock
everyone out of login), and request.scheme would say "http". Trusting exactly
one hop gives back the real client IP and scheme. It must stay at 1 -- trusting
more hops than really exist would let a visitor fake their IP by sending their
own X-Forwarded-For header. Local `python app.py` runs don't go through here,
since there is no proxy in front of them.
"""
from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app

app = create_app()
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
