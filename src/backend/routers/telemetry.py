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
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Telemetry, MonitoringSession
from core.dependencies import get_current_user
from core.cuid import generate_cuid
from core.csv_export import csv_response, parse_date_range

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

    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan")

    _get = lambda *keys: next((body[k] for k in keys if body.get(k) is not None), None)
    ph_level         = _get("ph_level", "phLevel")
    tds_value        = _get("tds_value", "tdsValue")
    dissolved_oxygen = _get("dissolved_oxygen", "dissolvedOxygen")
    water_temp       = _get("water_temp", "waterTemp")

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
        depth=float(body.get("depth") or 0.0),
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
# GET /api/telemetry/export — export CSV
# ==========================
@router.get("/export")
def export_telemetry(
    session_id: Optional[str] = None,
    from_: Optional[str] = Query(None, alias="from"),
    to_: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Export data telemetri ke CSV. Filter opsional: session_id, from, to (ISO 8601).
    """
    from_date, to_date = parse_date_range(from_, to_)

    query = db.query(Telemetry)
    if session_id:
        query = query.filter(Telemetry.session_id == session_id)
    if from_date:
        query = query.filter(Telemetry.timestamp >= from_date)
    if to_date:
        query = query.filter(Telemetry.timestamp <= to_date)

    rows = query.order_by(Telemetry.timestamp.desc()).all()

    header = ["id", "sessionId", "timestamp", "phLevel", "tdsValue", "dissolvedOxygen", "waterTemp", "depth", "createdAt"]
    data = [
        [t.id, t.session_id, t.timestamp.isoformat(), t.ph_level, t.tds_value, t.dissolved_oxygen, t.water_temp, t.depth, t.created_at.isoformat()]
        for t in rows
    ]

    filename = f"telemetry_export_{session_id or 'all'}.csv"
    return csv_response(filename, header, data)


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