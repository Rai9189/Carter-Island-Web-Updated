"""
Router telemetri — menggantikan:
  - src/app/api/telemetry/latest/route.ts  (GET latest)
  - src/app/api/telemetry/route.ts         (GET list, POST)
  - src/app/api/telemetry/fetch/route.ts   (DIHAPUS — diganti MAVLink langsung)

Endpoint /api/telemetry/fetch dihapus karena di pengembangan
selanjutnya telemetri akan diterima langsung via MAVLink di backend,
bukan di-fetch dari Raspberry Pi lewat HTTP.
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
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET data telemetri terbaru.
    Port dari src/app/api/telemetry/latest/route.ts
    """
    telemetry = db.query(Telemetry).order_by(Telemetry.timestamp.desc()).first()

    if not telemetry:
        raise HTTPException(status_code=404, detail="Tidak ada data telemetri")

    return {
        "success": True,
        "data": _format_telemetry(telemetry),
    }


# ==========================
# GET /api/telemetry — list dengan pagination
# ==========================
@router.get("")
def get_telemetry_list(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET list telemetri dengan pagination.
    Port dari src/app/api/telemetry/route.ts GET
    """
    total = db.query(Telemetry).count()
    telemetry_list = (
        db.query(Telemetry)
        .order_by(Telemetry.timestamp.desc())
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
# POST /api/telemetry — simpan data telemetri
# ==========================
@router.post("", status_code=status.HTTP_201_CREATED)
def save_telemetry(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    POST simpan data telemetri dari Raspberry Pi / MAVLink.
    Port dari src/app/api/telemetry/route.ts POST

    Perbaikan bug dari versi lama:
    - Versi lama pakai field gyroOk/accelOk/magOk (salah)
    - Versi baru pakai gyro_cal/accel_cal/mag_cal (sesuai schema)
    """
    attitude = body.get("attitude", {})
    compass = body.get("compass", {})
    battery = body.get("battery", {})
    health = body.get("health", {})

    if not all([attitude, compass, battery, health]):
        raise HTTPException(
            status_code=400,
            detail="Field attitude, compass, battery, health wajib diisi"
        )

    now = datetime.now(timezone.utc)
    telemetry = Telemetry(
        id=generate_cuid(),
        roll_deg=float(attitude.get("roll_deg", 0)),
        pitch_deg=float(attitude.get("pitch_deg", 0)),
        yaw_deg=float(attitude.get("yaw_deg", 0)),
        heading_deg=float(compass.get("heading_deg", 0)),
        voltage_v=float(battery.get("voltage_v", 0)),
        current_a=battery.get("current_a"),
        remaining_percent=float(battery.get("remaining_percent", 0)),
        consumed_mah=battery.get("consumed_mAh"),
        gyro_cal=bool(health.get("gyro_cal", False)),
        accel_cal=bool(health.get("accel_cal", False)),
        mag_cal=bool(health.get("mag_cal", False)),
        timestamp=now,
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
        "rollDeg": t.roll_deg,
        "pitchDeg": t.pitch_deg,
        "yawDeg": t.yaw_deg,
        "headingDeg": t.heading_deg,
        "voltageV": t.voltage_v,
        "currentA": t.current_a,
        "remainingPercent": t.remaining_percent,
        "consumedMah": t.consumed_mah,
        "gyroCal": t.gyro_cal,
        "accelCal": t.accel_cal,
        "magCal": t.mag_cal,
        "timestamp": t.timestamp.isoformat(),
        "createdAt": t.created_at.isoformat(),
    }