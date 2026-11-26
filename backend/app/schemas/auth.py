from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: str
    email: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None


class UserRegisterRequest(BaseModel):
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15, description="10-digit mobile number")
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: Optional[str] = "customer"  # customer or partner roles
    city_id: Optional[int] = None
    locality_id: Optional[int] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip().lower() in ["super_admin", "admin", "superadmin"]:
            raise ValueError("Public registration cannot assign administrative roles.")
        return v


class UserLoginRequest(BaseModel):
    login: str = Field(..., description="Email or mobile number")
    password: str = Field(..., min_length=1)


class OTPRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    purpose: str = "login"  # login, registration, password_reset


class OTPVerifyRequest(BaseModel):
    phone: str
    otp: str = Field(..., min_length=4, max_length=6)
    purpose: str = "login"


class ForgotPasswordRequest(BaseModel):
    email_or_phone: str


class ResetPasswordRequest(BaseModel):
    email_or_phone: str
    otp: str
    new_password: str = Field(..., min_length=6)


class UserProfileResponse(BaseModel):
    id: int
    email: str
    phone: str
    full_name: str
    is_active: bool
    is_verified: bool
    account_status: str = "ACTIVE"
    roles: List[str]
    avatar_url: Optional[str] = None
    city_name: Optional[str] = None
    city_id: Optional[int] = None
    locality_name: Optional[str] = None
    locality_id: Optional[int] = None
    preferred_language: Optional[str] = "English"
    bio: Optional[str] = None
    partner_id: Optional[int] = None
    partner_type: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    city_id: Optional[int] = None
    locality_id: Optional[int] = None
    preferred_language: Optional[str] = None
    bio: Optional[str] = None
    emergency_phone: Optional[str] = None

