"""
Pydantic schemas untuk endpoint autentikasi.
Dipakai untuk validasi request body.
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional

from core.validation import check_password, check_phone


# ==========================
# Request schemas
# ==========================
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    model_config = {"json_schema_extra": {
        "example": {
            "email": "admin@carterisland.com",
            "password": "password123"
        }
    }}


class RegisterRequest(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    phoneNumber: str
    role: Optional[str] = "USER"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        return check_password(v)

    @field_validator("phoneNumber")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        return check_phone(v.strip())

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in ("USER", "ADMIN"):
            raise ValueError("Role harus USER atau ADMIN")
        return v

    model_config = {"json_schema_extra": {
        "example": {
            "fullName": "John Doe",
            "email": "john@carterisland.com",
            "password": "password123",
            "phoneNumber": "08123456789",
            "role": "USER"
        }
    }}
