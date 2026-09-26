"""
JWT utility menggunakan python-jose.

Menggantikan NextAuth.js untuk autentikasi.
Token disimpan di frontend sebagai httpOnly cookie.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status

logger = logging.getLogger("carter-backend")

# Import dari config — pastikan config.py sudah ditambahkan config_additions.py
from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES


# ==========================
# Create token
# ==========================
def create_access_token(
    user_id: str,
    email: str,
    role: str,
    full_name: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Buat JWT access token.

    Args:
        user_id: ID user dari database
        email: Email user
        role: Role user ('USER' atau 'ADMIN')
        full_name: Nama tampilan — dibaca frontend (auth-utils.ts decodeJWT)
            untuk Sidebar/Dashboard. Hanya untuk tampilan, tidak dipakai
            backend; berubah di UI setelah login ulang.
        expires_delta: Override durasi expired (opsional)

    Returns:
        JWT token string

    Contoh:
        token = create_access_token(
            user_id="clh3qz8x2...",
            email="admin@carterisland.com",
            role="ADMIN"
        )
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,          # Subject — user ID
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # Issued at
    }
    if full_name:
        payload["fullName"] = full_name

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


# ==========================
# Verify token
# ==========================
def verify_token(token: str) -> dict:
    """
    Verifikasi dan decode JWT token.

    Args:
        token: JWT token string dari header Authorization

    Returns:
        Dict berisi payload token (sub, email, role, exp)

    Raises:
        HTTPException 401 jika token tidak valid atau expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah expired",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        role: str = payload.get("role")

        if user_id is None or email is None:
            logger.warning("Token payload tidak lengkap")
            raise credentials_exception

        # Refresh token lama (berlaku 7 hari, secret sama) tidak boleh dipakai
        # sebagai access token
        if payload.get("type") == "refresh":
            logger.warning("Refresh token ditolak sebagai access token")
            raise credentials_exception

        return {
            "user_id": user_id,
            "email": email,
            "role": role,
        }

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise credentials_exception
