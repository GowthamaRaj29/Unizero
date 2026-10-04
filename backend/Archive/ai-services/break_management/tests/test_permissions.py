import pytest

from break_management.permissions import (
    Action,
    PermissionDeniedError,
    Role,
    require_different_actors,
    require_permission,
)


def test_investigator_role_permits_submit_and_override():
    assert require_permission("jane", "INVESTIGATOR", Action.SUBMIT_CAUSE) == Role.INVESTIGATOR
    assert require_permission("jane", Role.INVESTIGATOR, Action.OVERRIDE_RCA) == Role.INVESTIGATOR


def test_investigator_role_cannot_authorize():
    with pytest.raises(PermissionDeniedError):
        require_permission("jane", "INVESTIGATOR", Action.AUTHORIZE_BREAK)


def test_approver_role_cannot_submit_cause():
    with pytest.raises(PermissionDeniedError):
        require_permission("bob", "APPROVER", Action.SUBMIT_CAUSE)


def test_approver_role_permits_authorize_bulk_and_upload():
    for action in (Action.AUTHORIZE_BREAK, Action.BULK_AUTHORIZE, Action.UPLOAD_APPROVALS):
        assert require_permission("bob", "APPROVER", action) == Role.APPROVER


def test_unknown_role_string_is_rejected():
    with pytest.raises(PermissionDeniedError):
        require_permission("mallory", "SUPERUSER", Action.AUTHORIZE_BREAK)


def test_missing_role_is_rejected():
    with pytest.raises(PermissionDeniedError):
        require_permission("mallory", "", Action.AUTHORIZE_BREAK)


def test_permission_checks_are_audited_both_allowed_and_denied():
    from break_management.permissions import PERMISSION_AUDIT_LOG

    require_permission("jane", "INVESTIGATOR", Action.SUBMIT_CAUSE)
    with pytest.raises(PermissionDeniedError):
        require_permission("jane", "INVESTIGATOR", Action.AUTHORIZE_BREAK)

    assert PERMISSION_AUDIT_LOG[-2]["allowed"] is True
    assert PERMISSION_AUDIT_LOG[-2]["actor"] == "jane"
    assert PERMISSION_AUDIT_LOG[-1]["allowed"] is False


def test_require_different_actors_blocks_same_maker_and_checker():
    with pytest.raises(PermissionDeniedError):
        require_different_actors("jane", "jane")


def test_require_different_actors_allows_different_people():
    require_different_actors("jane", "bob")  # must not raise


def test_require_different_actors_allows_no_maker_yet():
    require_different_actors(None, "bob")  # must not raise -- no finding submitted yet
