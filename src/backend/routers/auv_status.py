"""
Router AUV status — menggantikan:
  - src/app/api/auv-status/latest/route.ts  (GET latest)
  - src/app/api/auv-status/route.ts         (GET list, POST)
  - src/app/api/health/check/route.ts       (dipindah ke background task Fase 5)
  - src/app/api/mediamtx/health/route.ts    (dipindah ke background task Fase 5)
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

# IP Raspberry Pi dan MediaMTX — dipakai untuk health check manual
RASPI_TELEMETRY_URL = "http://192.168.2.2:14552/telemetry"
MEDIAMTX_URL = "http://192.168.2.2:8889/cam/"


# ==========================
# GET /api/auv-status/latest
# ==========================
@router.get("/latest")
def get_latest_auv_status(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET status AUV terbaru.
    Port dari src/app/api/auv-status/latest/route.ts
    """
    auv_status = db.query(AUVStatus).order_by(AUVStatus.timestamp.desc()).first()

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
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET list AUV status dengan pagination.
    Port dari src/app/api/auv-status/route.ts GET
    """
    total = db.query(AUVStatus).count()
    status_list = (
        db.query(AUVStatus)
        .order_by(AUVStatus.timestamp.desc())
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
# POST /api/auv-status — simpan status
# ==========================
@router.post("", status_code=status.HTTP_201_CREATED)
def save_auv_status(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    POST simpan AUV status.
    Port dari src/app/api/auv-status/route.ts POST
    """
    is_online = body.get("isOnline")
    connection_strength = body.get("connectionStrength", "")
    uptime_seconds = body.get("uptimeSeconds")

    if is_online is None or not connection_strength or uptime_seconds is None:
        raise HTTPException(
            status_code=400,
            detail="isOnline, connectionStrength, uptimeSeconds wajib diisi"
        )

    now = datetime.now(timezone.utc)
    last_stream_time = None
    if body.get("lastStreamTime"):
        try:
            last_stream_time = datetime.fromisoformat(body["lastStreamTime"])
        except ValueError:
            pass

    new_status = AUVStatus(
        id=generate_cuid(),
        is_online=bool(is_online),
        connection_strength=str(connection_strength),
        uptime_seconds=int(uptime_seconds),
        location_status=body.get("locationStatus", "Active"),
        last_stream_time=last_stream_time,
        timestamp=now,
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
        "isOnline": s.is_online,
        "connectionStrength": s.connection_strength,
        "uptimeSeconds": s.uptime_seconds,
        "locationStatus": s.location_status,
        "lastStreamTime": s.last_stream_time.isoformat() if s.last_stream_time else None,
        "timestamp": s.timestamp.isoformat(),
        "createdAt": s.created_at.isoformat(),
    }