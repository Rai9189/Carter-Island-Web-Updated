"""
Router AUV status — data navigasi & attitude ROV dari IMU Pixhawk.

Perubahan dari versi lama:
  - Field lama (is_online, connection_strength, uptime_seconds) → dihapus
  - Field baru: roll, pitch, yaw, depth, heading, speed, gyroscope, accel, magnet
  - POST payload disesuaikan dengan data navigasi IMU
  - session_id sekarang wajib (FK ke monitoring_sessions)
  - Endpoint health check manual dihapus (sudah digantikan scheduler)
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import AUVStatus
from core.dependencies import get_current_user
from core.cuid import generate_cuid

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/auv-status", tags=["AUV Status"])


# ==========================
# GET /api/auv-status/latest
# ==========================
@router.get("/latest")
def get_latest_auv_status(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET data navigasi AUV terbaru.
    Opsional filter by session_id.
    """
    query = db.query(AUVStatus).order_by(AUVStatus.timestamp.desc())

    if session_id:
        query = query.filter(AUVStatus.session_id == session_id)

    auv_status = query.first()

    if not auv_status:
        raise HTTPException(status_code=404, detail="Tidak ada data AUV status")

    return {"success": True, "data": _format_status(auv_status)}


# ==========================
# GET /api/auv-status — list dengan pagination
# ==========================
@router.get("")
def get_auv_status_list(
    limit: int = 10,
    offset: int = 0,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET list data navigasi AUV dengan pagination.
    """
    query = db.query(AUVStatus)

    if session_id:
        query = query.filter(AUVStatus.session_id == session_id)

    total = query.count()
    status_list = (
        query.order_by(AUVStatus.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": [_format_status(s) for s in status_list],
        "pagination": {"total": total, "limit": limit, "offset": offset},
    }


# ==========================
# POST /api/auv-status — simpan data navigasi
# ==========================
@router.post("", status_code=status.HTTP_201_CREATED)
def save_auv_status(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    POST simpan data navigasi & attitude ROV dari IMU Pixhawk.

    Payload:
        session_id    : str   — wajib, FK ke monitoring_sessions
        roll          : float — rotasi sumbu X (deg)
        pitch         : float — rotasi sumbu Y (deg)
        yaw           : float — rotasi sumbu Z (deg)
        depth         : float — kedalaman (meter)
        heading       : str   — arah kompas (N/NE/E/SE/S/SW/W/NW atau derajat)
        speed         : float — kecepatan (m/s)
        gyroscope     : str   — JSON string data mentah gyroscope (opsional)
        accelerometer : str   — JSON string data mentah accelerometer (opsional)
        magnetometer  : str   — JSON string data mentah magnetometer (opsional)
    """
    session_id = body.get("session_id") or body.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id wajib diisi")

    now = datetime.now(timezone.utc)

    new_status = AUVStatus(
        id=generate_cuid(),
        session_id=session_id,
        timestamp=now,
        roll=float(body.get("roll", 0.0)),
        pitch=float(body.get("pitch", 0.0)),
        yaw=float(body.get("yaw", 0.0)),
        depth=float(body.get("depth", 0.0)),
        heading=str(body.get("heading", "N")),
        speed=float(body.get("speed", 0.0)),
        gyroscope=body.get("gyroscope"),
        accelerometer=body.get("accelerometer"),
        magnetometer=body.get("magnetometer"),
        created_at=now,
    )

    db.add(new_status)
    db.commit()
    db.refresh(new_status)

    return {"success": True, "data": _format_status(new_status)}


# ==========================
# Helper
# ==========================
def _format_status(s: AUVStatus) -> dict:
    return {
        "id": s.id,
        "sessionId": s.session_id,
        "timestamp": s.timestamp.isoformat(),
        "roll": s.roll,
        "pitch": s.pitch,
        "yaw": s.yaw,
        "depth": s.depth,
        "heading": s.heading,
        "speed": s.speed,
        "gyroscope": s.gyroscope,
        "accelerometer": s.accelerometer,
        "magnetometer": s.magnetometer,
        "createdAt": s.created_at.isoformat(),
    }