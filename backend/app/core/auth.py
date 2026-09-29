from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.db.client import get_supabase_client
from app.schemas.auth import AppRole, AuthContext, AuthenticatedUser, UserProfile


bearer_scheme = HTTPBearer(auto_error=False)


def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None:
        raise _auth_error()

    try:
        response: Any = get_supabase_client().auth.get_user(credentials.credentials)
        auth_user = response.user
        if auth_user is None:
            raise _auth_error()
        return AuthenticatedUser(id=str(auth_user.id), email=auth_user.email)
    except HTTPException:
        raise
    except Exception as error:
        if settings.supabase_url and settings.supabase_service_role_key:
            raise _auth_error() from error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured",
        ) from error


def get_current_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserProfile:
    try:
        response: Any = (
            get_supabase_client()
            .table("users")
            .select("id, email, display_name, role")
            .eq("id", current_user.id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is authenticated, but its SkillUp profile has not been provisioned. Contact an administrator.",
            )
        return UserProfile.model_validate(response.data)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile service is unavailable",
        ) from error


def require_role(*allowed_roles: AppRole) -> Callable[..., UserProfile]:
    def role_dependency(
        profile: UserProfile = Depends(get_current_profile),
    ) -> UserProfile:
        if profile.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return profile

    return role_dependency


def get_auth_context(
    current_user: AuthenticatedUser = Depends(get_current_user),
    profile: UserProfile = Depends(get_current_profile),
) -> AuthContext:
    return AuthContext(user=current_user, profile=profile)
