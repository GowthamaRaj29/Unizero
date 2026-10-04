"""
Requirement 8: Maker-Checker -- role/action permission enforcement.

Bugfix history, stated plainly because it explains the shape of this
module: an earlier version had require_permission() take the caller's
claimed role and check it straight against ROLE_PERMISSIONS -- i.e. it
trusted whatever role value showed up in the request. That's the "loophole"
being fixed here (#8): a permission layer that just believes a client-
supplied string isn't enforcing anything.

The fix is a single seam: resolve_role(actor, claimed_role). Today it
still has nothing but the client-claimed role to go on -- there is no
real authentication in this codebase yet (same honest gap noted in
ingestion/workflow.py's own docstring) -- so it cannot yet *verify*
identity. What it DOES do is make that limitation explicit and
contained to one function: every audit entry records the role's
`source` ("client_claimed" today), and wiring in real auth/RBAC later
(a verified session, a JWT claim, a lookup against a trusted user
store) means replacing resolve_role()'s body only. Nothing in
service.py, api.py, or require_permission()'s own signature needs to
change for that swap -- they already only deal with a resolved Role,
never a raw claimed string.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class Role(str, Enum):
    INVESTIGATOR = "INVESTIGATOR"
    APPROVER = "APPROVER"


class Action(str, Enum):
    SUBMIT_CAUSE = "SUBMIT_CAUSE"
    OVERRIDE_RCA = "OVERRIDE_RCA"
    AUTHORIZE_BREAK = "AUTHORIZE_BREAK"
    BULK_AUTHORIZE = "BULK_AUTHORIZE"
    UPLOAD_APPROVALS = "UPLOAD_APPROVALS"


#: What each role may do. An action not listed for a role is denied for
#: that role -- there is no implicit/default-allow.
ROLE_PERMISSIONS: dict[Role, set[Action]] = {
    Role.INVESTIGATOR: {Action.SUBMIT_CAUSE, Action.OVERRIDE_RCA},
    Role.APPROVER: {Action.AUTHORIZE_BREAK, Action.BULK_AUTHORIZE, Action.UPLOAD_APPROVALS},
}


class PermissionDeniedError(Exception):
    """Raised for a missing/unknown/unresolvable role, or an action that
    role does not permit."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


#: Every permission check, granted or denied -- the audit trail for "who
#: (actor) had what role resolved for them, from what source, tried to
#: do what, and were they allowed."
PERMISSION_AUDIT_LOG: list[dict] = []


def _default_resolve_role(actor: str, claimed_role: Role | str | None) -> Role:
    """DEV-MODE DEFAULT ONLY -- not a real authorization decision.
    Validates that claimed_role is a syntactically real Role and
    returns it; does not check it against anything the actor is
    actually entitled to, because there is no trusted identity/session
    system in this codebase to check it against yet. This is exactly
    the gap Requirement 8.8 flags as needing to stay swappable -- see
    module docstring and ROLE_RESOLVER below."""
    if claimed_role is None or claimed_role == "":
        raise PermissionDeniedError("No role supplied for this action")
    try:
        return Role(claimed_role)
    except ValueError:
        raise PermissionDeniedError(
            f"Unknown role {claimed_role!r}; must be one of {[r.value for r in Role]}"
        ) from None


#: THE seam a real auth/RBAC integration replaces. Swap this module-level
#: callable (e.g. `permissions.ROLE_RESOLVER = my_trusted_resolver`) with
#: a function that resolves `actor`'s role from a verified source
#: (session, JWT claims, a user/role database behind real auth) and
#: ignores or cross-checks `claimed_role` instead of trusting it outright.
#: Everything downstream of resolve_role (require_permission, and every
#: service.py function that calls it) is already written against "a
#: resolved Role", not "a role the client typed in a JSON body", so no
#: other code changes when this is swapped.
ROLE_RESOLVER: Callable[[str, "Role | str | None"], Role] = _default_resolve_role


def resolve_role(actor: str, claimed_role: Role | str | None) -> Role:
    return ROLE_RESOLVER(actor, claimed_role)


def require_permission(actor: str, role: Role | str | None, action: Action) -> Role:
    """The single choke point every permissioned service function calls
    through. Resolves `role` via resolve_role() (see module docstring --
    this is the not-yet-trusted step) and checks the RESULT against
    ROLE_PERMISSIONS for `action`. Raises PermissionDeniedError on any
    failure; always logs the attempt, allowed or not."""
    try:
        resolved = resolve_role(actor, role)
    except PermissionDeniedError as exc:
        PERMISSION_AUDIT_LOG.append({
            "timestamp": _now(), "actor": actor, "action": action.value,
            "role": None, "role_source": "client_claimed", "allowed": False, "reason": str(exc),
        })
        raise

    allowed = action in ROLE_PERMISSIONS.get(resolved, set())
    PERMISSION_AUDIT_LOG.append({
        "timestamp": _now(), "actor": actor, "action": action.value,
        "role": resolved.value, "role_source": "client_claimed", "allowed": allowed,
        "reason": None if allowed else f"role {resolved.value} may not perform {action.value}",
    })
    if not allowed:
        raise PermissionDeniedError(
            f"Role {resolved.value} (actor {actor!r}) is not permitted to {action.value}"
        )
    return resolved


def require_different_actors(maker: str | None, checker: str) -> None:
    """The core of maker-checker, independent of roles: whoever proposed
    a resolution cannot also be the one who authorizes it. A None maker
    is handled by the caller (service._do_authorize requires a finding
    to exist at all before this is even reached -- see bugfix #2), so by
    the time this runs in practice maker is never None; the None-safe
    check is kept anyway so this function is correct standing alone."""
    if maker is not None and maker == checker:
        PERMISSION_AUDIT_LOG.append({
            "timestamp": _now(), "actor": checker, "action": "maker_checker.segregation",
            "role": None, "role_source": None, "allowed": False,
            "reason": f"actor {checker!r} cannot authorize a break they submitted the cause for",
        })
        raise PermissionDeniedError(
            f"Maker-checker violation: {checker!r} submitted this break's cause and cannot also authorize it"
        )
