"""
Router users — menggantikan:
  - src/app/api/users/route.ts         (GET list, POST create)
  - src/app/api/users/[id]/route.ts    (GET, PUT, DELETE by id)

Semua endpoint Admin only via require_admin() dependency.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import EmailStr, TypeAdapter, ValidationError

from database.connection import get_db
from database.models import User, Role, MonitoringSession
from auth.password import hash_password
from core.dependencies import require_admin
from core.cuid import generate_cuid
from core.validation import safe_str, check_password

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/users", tags=["Users"])

_email_adapter = TypeAdapter(EmailStr)


# ==========================
# Helper
# ==========================
def _read_user_body(body: dict, default_role: str) -> tuple[str, str, str, str, str]:
    """
    Ambil & validasi tipe field user dari body mentah → 400 kalau salah.
    Return (username, email, phone_number, role, password). Password tidak
    di-strip (di-hash apa adanya); cek panjangnya diserahkan ke caller karena
    di update password kosong berarti tidak diganti.
    """
    try:
        username = safe_str(body.get("fullName"), "fullName")
        email = safe_str(body.get("email"), "email").lower()
        phone_number = safe_str(body.get("phoneNumber"), "phoneNumber")
        password = body.get("password") or ""
        if not isinstance(password, str):
            raise ValueError("password harus berupa teks")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    role = body.get("role") or default_role
    if role not in ("USER", "ADMIN"):
        raise HTTPException(status_code=400, detail="Role harus USER atau ADMIN")

    if email:
        try:
            _email_adapter.validate_python(email)
        except ValidationError:
            raise HTTPException(status_code=400, detail="Format email tidak valid")

    return username, email, phone_number, role, password


def _check_password_or_400(password: str) -> None:
    try:
        check_password(password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def _format_user(user: User) -> dict:
    return {
        "id": user.id,
        "fullName": user.username,
        "email": user.email,
        "phoneNumber": user.phone_number,
        "role": user.role.value,
        "createdAt": user.created_at.isoformat(),
        "updatedAt": user.updated_at.isoformat(),
    }


# ==========================
# GET /api/users — list dengan cursor pagination
# ==========================
@router.get("")
def get_users(
    cursor: Optional[str] = None,
    limit: int = 10,
    sort: str = "desc",
    role: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """
    GET list users dengan cursor pagination.
    Port dari src/app/api/users/route.ts GET
    """
    valid_limit = min(max(limit, 1), 50)
    sort_order = sort if sort in ("asc", "desc") else "desc"

    query = db.query(User)

    # Filter role
    if role and role in ("USER", "ADMIN"):
        query = query.filter(User.role == Role(role))

    # Filter search
    if search:
        query = query.filter(
            or_(
                User.username.contains(search),
                User.email.contains(search),
            )
        )

    # Cursor pagination
    if cursor:
        if sort_order == "desc":
            query = query.filter(User.id < cursor)
        else:
            query = query.filter(User.id > cursor)

    # Sort
    if sort_order == "desc":
        query = query.order_by(User.created_at.desc(), User.id.desc())
    else:
        query = query.order_by(User.created_at.asc(), User.id.asc())

    users = query.limit(valid_limit + 1).all()

    has_more = len(users) > valid_limit
    items = users[:valid_limit]
    next_cursor = items[-1].id if has_more and items else None

    return {
        "items": [_format_user(u) for u in items],
        "nextCursor": next_cursor,
        "hasMore": has_more,
        "pagination": {
            "limit": valid_limit,
            "total": len(items),
            "sortOrder": sort_order,
            "filters": {"role": role, "search": search},
        },
    }


# ==========================
# POST /api/users — create user (Admin)
# ==========================
@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    POST create user baru oleh admin.
    Port dari src/app/api/users/route.ts POST
    """
    username, email, phone_number, role, password = _read_user_body(body, "USER")

    if not all([username, email, password, phone_number]):
        raise HTTPException(status_code=400, detail="Semua field wajib diisi")

    _check_password_or_400(password)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")

    now = datetime.now(timezone.utc)
    new_user = User(
        id=generate_cuid(),
        username=username,
        email=email,
        password=hash_password(password),
        phone_number=phone_number,
        role=Role(role),
        created_at=now,
        updated_at=now,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"User created: {new_user.email} by admin: {current_user['email']}")
    return {"message": "User created successfully", "user": _format_user(new_user)}


# ==========================
# GET /api/users/{id}
# ==========================
@router.get("/{user_id}")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """
    GET single user by ID.
    Port dari src/app/api/users/[id]/route.ts GET
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    return _format_user(user)


# ==========================
# PUT /api/users/{id}
# ==========================
@router.put("/{user_id}")
def update_user(
    user_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    PUT update user.
    Port dari src/app/api/users/[id]/route.ts PUT
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    username, email, phone_number, role, password = _read_user_body(body, user.role.value)

    if not all([username, email, phone_number]):
        raise HTTPException(
            status_code=400,
            detail="fullName, email, dan phoneNumber wajib diisi"
        )

    # Password kosong = tidak diganti
    if password.strip():
        _check_password_or_400(password)

    # Cek email tidak dipakai user lain
    if email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email sudah dipakai")

    user.username = username
    user.email = email
    user.phone_number = phone_number
    user.role = Role(role)
    user.updated_at = datetime.now(timezone.utc)

    if password and password.strip():
        user.password = hash_password(password)

    db.commit()
    db.refresh(user)

    logger.info(f"User updated: {user.id} by admin: {current_user['email']}")
    return {"message": "User updated successfully", "user": _format_user(user)}


# ==========================
# DELETE /api/users/{id}
# ==========================
@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    DELETE user by ID.
    Port dari src/app/api/users/[id]/route.ts DELETE
    Cegah self-deletion. Misi milik user dialihkan ke admin yang menghapus
    agar data survei tidak ikut terhapus (FK sessions.user_id ON DELETE CASCADE).
    """
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=400,
            detail="Tidak bisa menghapus akun sendiri"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    email = user.email
    username = user.username

    # Alihkan misi dulu — kalau tidak, cascade di DB ikut menghapus semua
    # telemetri, deteksi, dan rekaman misi user ini
    reassigned = (
        db.query(MonitoringSession)
        .filter(MonitoringSession.user_id == user_id)
        .update({MonitoringSession.user_id: current_user["id"]}, synchronize_session=False)
    )
    db.delete(user)
    db.commit()

    logger.info(
        f"User deleted: {user_id} ({email}) by admin: {current_user['email']}, "
        f"{reassigned} misi dialihkan ke admin tersebut"
    )
    message = f'User "{username}" berhasil dihapus'
    if reassigned:
        message += f"; {reassigned} misi dialihkan ke akun Anda"
    return {"message": message, "reassignedSessions": reassigned}