from contextvars import ContextVar


_current_user_id = ContextVar(
    "current_user_id",
    default=None,
)


def set_current_user_id(user_id):
    """Set the user ID for the current application context."""

    return _current_user_id.set(user_id)


def get_current_user_id():
    """Return the user ID for the current application context."""

    return _current_user_id.get()


def clear_current_user_id():
    """Clear the current application user context."""

    _current_user_id.set(None)