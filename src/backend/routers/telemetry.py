"""
Router telemetri — data kualitas air dari sensor ROV.

Perubahan dari versi lama:
  - Field lama (roll_deg, pitch_deg, battery, dll) → dihapus
  - Field baru: ph_level, tds_value, dissolved_oxygen, water_temp, depth
  - POST payload disesuaikan dengan sensor kualitas air
  - session_id sekarang wajib (FK ke monitoring_sessions)
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Telemetry
from core.dependencies import get_current_user
from core.cuid import generate_cuid

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])


# ==========================
# GET /api/telemetry/latest
# ==========================
@router.get("/latest")
def get_latest_telemetry(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET data kualitas air terbaru.
    Opsional filter by session_id.
    """
    query = db.query(Telemetry).order_by(Telemetry.timestamp.desc())

    if session_id:
        query = query.filter(Telemetry.session_id == session_id)

    telemetry = query.first()

    if not telemetry:
        raise HTTPException(status_code=404, detail="Tidak ada data telemetri")

    return {"success": True, "data": _format_telemetry(telemetry)}


# ==========================
# GET /api/telemetry — list dengan pagination
# ==========================
@router.get("")
def get_telemetry_list(
    limit: int = 10,
    offset: int = 0,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET list data kualitas air dengan pagination.
    """
    query = db.query(Telemetry)

    if session_id:
        query = query.filter(Telemetry.session_id == session_id)

    total = query.count()
    telemetry_list = (
        query.order_by(Telemetry.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": [_format_telemetry(t) for t in telemetry_list],
        "pagination": {"total": total, "limit": limit, "offset": offset},
    }


# ==========================
# POST /api/telemetry — simpan data kualitas air
# ==========================
@router.post("", status_code=status.HTTP_201_CREATED)
def save_telemetry(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    POST simpan data kualitas air dari sensor ROV.

    Payload:
        session_id       : str  — wajib, FK ke monitoring_sessions
        ph_level         : float
        tds_value        : float
        dissolved_oxygen : float
        water_temp       : float
        depth            : float (opsional, default 0.0)
    """
    session_id = body.get("session_id") or body.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id wajib diisi")

    ph_level         = body.get("ph_level") or body.get("phLevel")
    tds_value        = body.get("tds_value") or body.get("tdsValue")
    dissolved_oxygen = body.get("dissolved_oxygen") or body.get("dissolvedOxygen")
    water_temp       = body.get("water_temp") or body.get("waterTemp")

    if any(v is None for v in [ph_level, tds_value, dissolved_oxygen, water_temp]):
        raise HTTPException(
            status_code=400,
            detail="ph_level, tds_value, dissolved_oxygen, water_temp wajib diisi"
        )

    now = datetime.now(timezone.utc)
    telemetry = Telemetry(
        id=generate_cuid(),
        session_id=session_id,
        timestamp=now,
        depth=float(body.get("depth") or body.get("depth") or 0.0),
        ph_level=float(ph_level),
        tds_value=float(tds_value),
        dissolved_oxygen=float(dissolved_oxygen),
        water_temp=float(water_temp),
        created_at=now,
    )

    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)

    return {"success": True, "data": _format_telemetry(telemetry)}


# ==========================
# Helper
# ==========================
def _format_telemetry(t: Telemetry) -> dict:
    return {
        "id": t.id,
        "sessionId": t.session_id,
        "timestamp": t.timestamp.isoformat(),
        "depth": t.depth,
        "phLevel": t.ph_level,
        "tdsValue": t.tds_value,
        "dissolvedOxygen": t.dissolved_oxygen,
        "waterTemp": t.water_temp,
        "createdAt": t.created_at.isoformat(),
    }