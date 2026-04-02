"""
Pydantic schemas untuk endpoint autentikasi.
Dipakai untuk validasi request body dan format response.
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


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
        if len(v) < 6:
            raise ValueError("Password minimal 6 karakter")
        return v

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


# ==========================
# Response schemas
# ==========================
class UserResponse(BaseModel):
    id: str
    fullName: str
    email: str
    phoneNumber: str
    role: str
    createdAt: str
    updatedAt: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterResponse(BaseModel):
    success: bool
    message: str
    user: UserResponse