"""
Router analytics — sesuai models.py baru C300.

Perubahan dari versi lama:
  - FishDetection + DetectionDetail → Detection
  - Telemetry: kolom battery/attitude → ph_level/tds_value/dissolved_oxygen/water_temp/depth
  - AUVStatus: kolom is_online/uptime → roll/pitch/yaw/depth/heading/speed
  - Tambah endpoint: getSessionsByDate, getSessionById, getAllSessions,
                     getAuvStatusAnalytics (SPPI-41/42/43/44)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.connection import get_db
from database.models import Detection, Telemetry, AUVStatus, MonitoringSession, SessionStatus
from core.dependencies import get_current_user

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


# ==========================
# GET /api/analytics/detections
# SPPI-39 getDetectionAnalytics
# ==========================
@router.get("/detections")
def get_detection_analytics(
    hours: int = 24,
    session_id: Optional[str] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(Detection).filter(Detection.detected_at >= start_time)

    if session_id:
        query = query.filter(Detection.session_id == session_id)

    if date:
        try:
            dt = datetime.fromisoformat(date)
            query = query.filter(
                Detection.detected_at >= dt,
                Detection.detected_at < dt + timedelta(days=1),
            )
        except ValueError:
            pass

    detections = query.order_by(Detection.detected_at.asc()).all()

    # Agregasi per jam
    hourly: dict = {}
    species: dict = {}

    for d in detections:
        hour = d.detected_at.replace(minute=0, second=0, microsecond=0)
        hour_key = hour.isoformat()
        if hour_key not in hourly:
            hourly[hour_key] = {"count": 0}
        hourly[hour_key]["count"] += 1
        species[d.species_name] = species.get(d.species_name, 0) + 1

    total = len(detections)
    avg_conf = (
        sum(d.confidence for d in detections) / total if total else 0.0
    )

    return {
        "success": True,
        "data": {
            "summary": {
                "totalDetections": total,
                "avgConfidence": round(avg_conf, 4),
                "uniqueSpecies": len(species),
            },
            "timeSeries": [
                {"time": time, "detections": data["count"]}
                for time, data in hourly.items()
            ],
            "speciesDistribution": [
                {"species": sp, "count": cnt}
                for sp, cnt in sorted(species.items(), key=lambda x: -x[1])
            ],
        },
    }


# ==========================
# GET /api/analytics/telemetry
# SPPI-29/40 getTelemetryAnalytics
# ==========================
@router.get("/telemetry")
def get_telemetry_analytics(
    hours: int = 24,
    session_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(Telemetry).filter(Telemetry.timestamp >= start_time)

    if session_id:
        query = query.filter(Telemetry.session_id == session_id)

    if from_date:
        try:
            query = query.filter(
                Telemetry.timestamp >= datetime.fromisoformat(from_date)
            )
        except ValueError:
            pass

    if to_date:
        try:
            query = query.filter(
                Telemetry.timestamp <= datetime.fromisoformat(to_date)
            )
        except ValueError:
            pass

    telemetry = (
        query.order_by(Telemetry.timestamp.asc())
        .limit(500)
        .all()
    )

    latest = telemetry[-1] if telemetry else None
    count = len(telemetry)

    avg_ph  = sum(t.ph_level or 0 for t in telemetry) / count if count else 0
    avg_tds = sum(t.tds_value or 0 for t in telemetry) / count if count else 0
    avg_do  = sum(t.dissolved_oxygen or 0 for t in telemetry) / count if count else 0
    avg_temp = sum(t.water_temp or 0 for t in telemetry) / count if count else 0

    return {
        "success": True,
        "data": {
            "summary": {
                "avgPh": round(avg_ph, 2),
                "avgTds": round(avg_tds, 2),
                "avgDo": round(avg_do, 2),
                "avgTemp": round(avg_temp, 2),
                "dataPoints": count,
                "latestDepth": round(latest.depth, 2) if latest and latest.depth is not None else 0,
            },
            "ph": [
                {"time": t.timestamp.isoformat(), "value": round(t.ph_level or 0, 2)}
                for t in telemetry
            ],
            "tds": [
                {"time": t.timestamp.isoformat(), "value": round(t.tds_value or 0, 2)}
                for t in telemetry
            ],
            "dissolvedOxygen": [
                {"time": t.timestamp.isoformat(), "value": round(t.dissolved_oxygen or 0, 2)}
                for t in telemetry
            ],
            "temperature": [
                {"time": t.timestamp.isoformat(), "value": round(t.water_temp or 0, 2)}
                for t in telemetry
            ],
            "depth": [
                {"time": t.timestamp.isoformat(), "value": round(t.depth or 0, 2)}
                for t in telemetry
            ],
        },
    }


# ==========================
# GET /api/analytics/auv-status
# SPPI-41 getAuvStatusAnalytics
# ==========================
@router.get("/auv-status")
def get_auv_status_analytics(
    hours: int = 24,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(AUVStatus).filter(AUVStatus.timestamp >= start_time)

    if session_id:
        query = query.filter(AUVStatus.session_id == session_id)

    status_data = (
        query.order_by(AUVStatus.timestamp.asc())
        .limit(500)
        .all()
    )

    latest = status_data[-1] if status_data else None
    count = len(status_data)

    return {
        "success": True,
        "data": {
            "summary": {
                "dataPoints": count,
                "latestDepth": round(latest.depth, 2) if latest and latest.depth is not None else 0,
                "latestHeading": latest.heading if latest and latest.heading is not None else "N",
                "latestSpeed": round(latest.speed, 2) if latest and latest.speed is not None else 0,
            },
            "attitude": [
                {
                    "time": s.timestamp.isoformat(),
                    "roll": round(s.roll or 0, 2),
                    "pitch": round(s.pitch or 0, 2),
                    "yaw": round(s.yaw or 0, 2),
                }
                for s in status_data
            ],
            "navigation": [
                {
                    "time": s.timestamp.isoformat(),
                    "depth": round(s.depth or 0, 2),
                    "speed": round(s.speed or 0, 2),
                    "heading": s.heading or "N",
                }
                for s in status_data
            ],
        },
    }


# ==========================
# GET /api/analytics/sessions/by-date
# SPPI-42 getSessionsByDate
# ==========================
@router.get("/sessions/by-date")
def get_sessions_by_date(
    date: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Ambil daftar sesi berdasarkan tanggal.
    Digunakan untuk mengisi dropdown Misi di halaman Analytics.
    """
    try:
        dt = datetime.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal tidak valid. Gunakan YYYY-MM-DD")

    sessions = (
        db.query(MonitoringSession)
        .filter(
            MonitoringSession.start_time >= dt,
            MonitoringSession.start_time < dt + timedelta(days=1),
        )
        .order_by(MonitoringSession.start_time.asc())
        .all()
    )

    return {
        "success": True,
        "data": [_format_session(s) for s in sessions],
    }


# ==========================
# GET /api/analytics/sessions/{session_id}
# SPPI-43 getSessionById
# ==========================
@router.get("/sessions/{session_id}")
def get_session_by_id(
    session_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Ambil detail satu sesi berdasarkan ID.
    Digunakan halaman Analytics untuk label session setelah user memilih misi.
    """
    session = db.query(MonitoringSession).filter(
        MonitoringSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    return {"success": True, "data": _format_session(session)}


# ==========================
# GET /api/analytics/sessions
# SPPI-44 getAllSessions
# ==========================
@router.get("/sessions")
def get_all_sessions(
    status: Optional[str] = None,
    sort: str = "desc",
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Ambil seluruh sesi survei.
    Digunakan halaman Historical Data untuk tabel Riwayat Misi.
    """
    query = db.query(MonitoringSession)

    if status:
        try:
            query = query.filter(MonitoringSession.status == SessionStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Status tidak valid. Gunakan: Running, Completed, atau Aborted")

    if sort == "asc":
        query = query.order_by(MonitoringSession.start_time.asc())
    else:
        query = query.order_by(MonitoringSession.start_time.desc())

    sessions = query.all()

    # Rata-rata telemetri per sesi dalam 1 query, agar tabel Riwayat Misi
    # tidak perlu 1 request per baris (N+1)
    avg_rows = (
        db.query(
            Telemetry.session_id,
            func.avg(Telemetry.ph_level),
            func.avg(Telemetry.tds_value),
            func.avg(Telemetry.water_temp),
            func.avg(Telemetry.dissolved_oxygen),
        )
        .group_by(Telemetry.session_id)
        .all()
    )
    _round = lambda v: round(float(v), 2) if v is not None else None
    avg_map = {
        sid: {"avgPh": _round(ph), "avgTds": _round(tds), "avgTemp": _round(temp), "avgDo": _round(do)}
        for sid, ph, tds, temp, do in avg_rows
    }
    empty_avg = {"avgPh": None, "avgTds": None, "avgTemp": None, "avgDo": None}

    return {
        "success": True,
        "data": [{**_format_session(s), **avg_map.get(s.id, empty_avg)} for s in sessions],
        "total": len(sessions),
    }


# ==========================
# Helper
# ==========================
def _format_session(s: MonitoringSession) -> dict:
    return {
        "id": s.id,
        "userId": s.user_id,
        "locationName": s.location_name,
        "startTime": s.start_time.isoformat(),
        "endTime": s.end_time.isoformat() if s.end_time else None,
        "status": s.status.value,
        "createdAt": s.created_at.isoformat(),
        "updatedAt": s.updated_at.isoformat(),
    }