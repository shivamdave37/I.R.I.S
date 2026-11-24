"""Hold a short-lived approval grant for normal, trusted in-process dispatch.

This context protects ordinary calls into skills from accidentally skipping the
gateway. It is not a security boundary against malicious Python code already
running in the Iris process: Python modules and objects are introspectable.
"""

from contextlib import contextmanager
from contextvars import ContextVar
import json


_CURRENT_ACTION = ContextVar("iris_current_approved_action", default=None)
_GATEWAY_CAPABILITY = object()


def _fingerprint(action, params):
    """Create a stable comparison value for one action and its exact parameters."""
    return action, json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@contextmanager
def _grant(action, params, *, capability=None):
    """Temporarily mark a gateway-dispatched action; ordinary direct use fails."""
    if capability is not _GATEWAY_CAPABILITY:
        raise PermissionError("Only the action gateway can create an approval grant.")
    token = _CURRENT_ACTION.set(_fingerprint(action, params))
    try:
        yield
    finally:
        _CURRENT_ACTION.reset(token)


def require(action, params):
    """Reject a state-changing skill call outside its approved gateway dispatch."""
    if _CURRENT_ACTION.get() != _fingerprint(action, params):
        raise PermissionError("This action must be run through Iris's approval gateway.")
