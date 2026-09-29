from typing import Literal

from pydantic import BaseModel, ConfigDict


AppRole = Literal["learner", "business", "admin"]


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None = None


class UserProfile(AuthenticatedUser):
    display_name: str | None = None
    role: AppRole


class AuthContext(BaseModel):
    user: AuthenticatedUser
    profile: UserProfile
