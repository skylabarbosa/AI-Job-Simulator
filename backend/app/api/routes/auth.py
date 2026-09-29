from fastapi import APIRouter, Depends

from app.core.auth import get_auth_context
from app.schemas.auth import AuthContext


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthContext)
def authenticated_user(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    return auth_context
