from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.core.auth import get_current_profile, require_role
from app.schemas.auth import AuthenticatedUser, UserProfile


def _profile_query(data):
    client = Mock()
    query = client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    query.execute.return_value = SimpleNamespace(data=data)
    return client, query


def test_current_profile_looks_up_by_authenticated_uid():
    user_id = "84d0f19d-155b-425d-865b-614c02f21782"
    row = {
        "id": user_id,
        "email": "business@example.test",
        "display_name": "Business",
        "role": "business",
    }
    client, query = _profile_query(row)

    with patch("app.core.auth.get_supabase_client", return_value=client):
        profile = get_current_profile(AuthenticatedUser(id=user_id))

    assert profile.id == user_id
    assert profile.role == "business"
    client.table.assert_called_once_with("users")
    client.table.return_value.select.assert_called_once_with("id, email, display_name, role")
    client.table.return_value.select.return_value.eq.assert_called_once_with("id", user_id)
    query.execute.assert_called_once_with()


def test_current_profile_reports_missing_provisioning_clearly():
    client, _ = _profile_query(None)

    with patch("app.core.auth.get_supabase_client", return_value=client):
        with pytest.raises(HTTPException) as error:
            get_current_profile(AuthenticatedUser(id="missing-user-id"))

    assert error.value.status_code == 403
    assert error.value.detail == (
        "Your account is authenticated, but its SkillUp profile has not been provisioned. "
        "Contact an administrator."
    )


@pytest.mark.parametrize(
    ("actual_role", "allowed_roles", "authorized"),
    [
        ("learner", ("learner",), True),
        ("business", ("business",), True),
        ("learner", ("business",), False),
        ("business", ("learner",), False),
        ("admin", ("admin",), True),
    ],
)
def test_role_guard_enforces_the_stored_profile_role(actual_role, allowed_roles, authorized):
    profile = UserProfile(
        id="authenticated-user-id",
        email="user@example.test",
        role=actual_role,
    )
    guard = require_role(*allowed_roles)

    if authorized:
        assert guard(profile) is profile
    else:
        with pytest.raises(HTTPException) as error:
            guard(profile)
        assert error.value.status_code == 403
        assert error.value.detail == "You do not have permission to access this resource"