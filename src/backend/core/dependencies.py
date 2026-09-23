"""
FastAPI dependency injection untuk autentikasi.

Menggantikan getServerSession(authOptions) dari NextAuth.

Cara pakai di router:
    # Route yang butuh login
    @router.get("/protected")
    def protected(current_user = Depends(get_current_user)):
        return {"user": current_user["email"]}

    # Route khusus admin
    @router.get("/admin-only")
    def admin_only(current_user = Depends(require_admin)):
        return {"admin": current_user["email"]}
"""
import logging
import secrets
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from auth.jwt import verify_token
from config import BASE_STATION_SYNC_TOKEN

logger = logging.getLogger("carter-backend")

# Bearer token extractor dari header Authorization
bearer_scheme = HTTPBearer(auto_error=False)


# ==========================
# Extract token dari request
# ==========================
def get_token_from_request(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    request: Request = None,
) -> Optional[str]:
    """
    Extract JWT token dari:
    1. Header Authorization: Bearer <token>  (prioritas utama)
    2. Cookie 'access_token' (fallback untuk browser)
    """
    # Dari header Authorization
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials

    # Dari cookie (fallback)
    if request:
        token = request.cookies.get("access_token")
        if token:
            return token

    return None


# ==========================
# Dependency: get_current_user
# ==========================
def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """
    Dependency untuk route yang butuh user login.
    Verifikasi JWT token dan return data user dari DB.

    Raises:
        HTTPException 401 jika tidak ada token atau token tidak valid
        HTTPException 404 jika user tidak ditemukan di DB
    """
    # Extract token
    token = get_token_from_request(credentials, request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak ditemukan. Silakan login terlebih dahulu.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verifikasi token
    payload = verify_token(token)

    # Cek user masih ada di DB
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak ditemukan",
        )

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role.value,
        "phone_number": user.phone_number,
    }


# ==========================
# Dependency: require_admin
# ==========================
def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Dependency untuk route khusus ADMIN.
    Menggantikan: if (!session || session.user.role !== 'ADMIN')

    Raises:
        HTTPException 403 jika user bukan admin
    """
    if current_user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak. Hanya admin yang diizinkan.",
        )
    return current_user


# ==========================
# Dependency: verify_sync_token
# ==========================
def verify_sync_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    request: Request = None,
) -> None:
    """
    Dependency untuk endpoint sync SPPI (ROV -> Base Station).
    Bandingkan token langsung ke BASE_STATION_SYNC_TOKEN (static shared
    secret) pakai secrets.compare_digest (constant-time, cegah timing
    attack) - TIDAK lewat verify_token()/tabel User seperti JWT user biasa.

    Raises:
        HTTPException 401 jika token tidak ada, kosong, atau tidak cocok
        HTTPException 500 jika BASE_STATION_SYNC_TOKEN belum dikonfigurasi
    """
    if not BASE_STATION_SYNC_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BASE_STATION_SYNC_TOKEN belum dikonfigurasi di server ini.",
        )

    token = get_token_from_request(credentials, request)

    if not token or not secrets.compare_digest(token, BASE_STATION_SYNC_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sync token tidak valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==========================
# Dependency: get_current_user_optional
# ==========================
def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[dict]:
    """
    Versi optional dari get_current_user.
    Dipakai di route yang bisa diakses dengan atau tanpa login.
    Return None kalau tidak ada token (tidak raise error).
    """
    try:
        return get_current_user(request, credentials, db)
    except HTTPException:
        return None