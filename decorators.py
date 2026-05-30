"""
BanaaIQ role-based access decorator.

Usage:
    from decorators import role_required
    from models import ROLE_PROJECT_MANAGER, ROLE_SITE_ENGINEER

    @app.route("/projects/create", methods=["GET", "POST"])
    @login_required          # outermost: redirects unauthenticated users to login
    @role_required(ROLE_PROJECT_MANAGER)   # inner: aborts 403 if wrong role
    def projects_create():
        ...

Decorator order:
    @login_required must be the OUTERMOST decorator so Flask-Login handles
    unauthenticated requests (redirect to login) before role_required ever
    runs.  role_required sits inside login_required and can assume that
    current_user is authenticated.
"""

from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*allowed_roles):
    """Abort with 403 if current_user.role is not in *allowed_roles*.

    Must be applied INSIDE (i.e. below) @login_required so that
    current_user is guaranteed to be authenticated.

    Examples::

        @login_required
        @role_required(ROLE_PROJECT_MANAGER)
        def pm_only_view(): ...

        @login_required
        @role_required(ROLE_PROJECT_MANAGER, ROLE_SITE_ENGINEER)
        def shared_view(): ...
    """
    def decorator(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            if not current_user.is_authenticated:
                # Shouldn't reach here if @login_required is outermost,
                # but guard defensively.
                abort(401)
            if getattr(current_user, "role", None) not in allowed_roles:
                abort(403)
            return fn(*args, **kwargs)
        return inner
    return decorator
