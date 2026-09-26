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
import math
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, literal_column

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
    conds = [Detection.detected_at >= start_time]

    if session_id:
        conds.append(Detection.session_id == session_id)

    if date:
        try:
            dt = datetime.fromisoformat(date)
            conds += [
                Detection.detected_at >= dt,
                Detection.detected_at < dt + timedelta(days=1),
            ]
        except ValueError:
            pass

    # Semua agregasi di SQL — deteksi YOLO bisa sangat banyak, jangan
    # dimuat ke memori.
    total, avg_conf = (
        db.query(func.count(Detection.id), func.avg(Detection.confidence))
        .filter(*conds)
        .one()
    )

    # Format jam sama dengan datetime.isoformat() naive: 2026-09-25T10:00:00
    hour_key = func.date_format(Detection.detected_at, "%Y-%m-%dT%H:00:00")
    hourly = (
        db.query(hour_key, func.count(Detection.id))
        .filter(*conds)
        .group_by(hour_key)
        .order_by(hour_key)
        .all()
    )

    # Seri: jumlah terbanyak dulu, sama banyak → spesies yang muncul duluan
    species = (
        db.query(Detection.species_name, func.count(Detection.id))
        .filter(*conds)
        .group_by(Detection.species_name)
        .order_by(func.count(Detection.id).desc(), func.min(Detection.detected_at))
        .all()
    )

    return {
        "success": True,
        "data": {
            "summary": {
                "totalDetections": total,
                "avgConfidence": round(float(avg_conf or 0.0), 4),
                "uniqueSpecies": len(species),
            },
            "timeSeries": [
                {"time": time, "detections": cnt}
                for time, cnt in hourly
            ],
            "speciesDistribution": [
                {"species": sp, "count": cnt}
                for sp, cnt in species
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
    conds = [Telemetry.timestamp >= start_time]

    if session_id:
        conds.append(Telemetry.session_id == session_id)

    if from_date:
        try:
            conds.append(Telemetry.timestamp >= datetime.fromisoformat(from_date))
        except ValueError:
            pass

    if to_date:
        try:
            conds.append(Telemetry.timestamp <= datetime.fromisoformat(to_date))
        except ValueError:
            pass

    # Ringkasan dari SELURUH rentang (dulu cuma 500 baris pertama)
    count, avg_ph, avg_tds, avg_do, avg_temp, first_ts, last_ts = (
        db.query(
            func.count(Telemetry.id),
            func.avg(Telemetry.ph_level),
            func.avg(Telemetry.tds_value),
            func.avg(Telemetry.dissolved_oxygen),
            func.avg(Telemetry.water_temp),
            func.min(Telemetry.timestamp),
            func.max(Telemetry.timestamp),
        )
        .filter(*conds)
        .one()
    )
    latest_depth = (
        db.query(Telemetry.depth)
        .filter(*conds)
        .order_by(Telemetry.timestamp.desc())
        .limit(1)
        .scalar()
    )

    series = _telemetry_series(db, conds, count, first_ts, last_ts)
    _r = lambda v: round(float(v or 0), 2)

    return {
        "success": True,
        "data": {
            "summary": {
                "avgPh": _r(avg_ph),
                "avgTds": _r(avg_tds),
                "avgDo": _r(avg_do),
                "avgTemp": _r(avg_temp),
                "dataPoints": count,
                "latestDepth": _r(latest_depth),
            },
            "ph": [{"time": s[0], "value": _r(s[1])} for s in series],
            "tds": [{"time": s[0], "value": _r(s[2])} for s in series],
            "dissolvedOxygen": [{"time": s[0], "value": _r(s[3])} for s in series],
            "temperature": [{"time": s[0], "value": _r(s[4])} for s in series],
            "depth": [{"time": s[0], "value": _r(s[5])} for s in series],
        },
    }


# Batas titik grafik per respons (ukuran payload tetap kecil)
TELEMETRY_MAX_POINTS = 500


def _telemetry_series(db: Session, conds: list, count: int, first_ts, last_ts) -> list:
    """
    Titik grafik telemetri yang mencakup seluruh rentang waktu.

    ≤ TELEMETRY_MAX_POINTS baris → semua baris apa adanya. Lebih dari itu →
    rentang dibagi rata jadi maksimal TELEMETRY_MAX_POINTS ember waktu, tiap
    titik = rata-rata ember, waktunya = timestamp pertama di ember.
    Return list (iso_time, ph, tds, do, temp, depth) urut waktu.
    """
    cols = (
        Telemetry.ph_level, Telemetry.tds_value, Telemetry.dissolved_oxygen,
        Telemetry.water_temp, Telemetry.depth,
    )
    if count <= TELEMETRY_MAX_POINTS:
        rows = (
            db.query(Telemetry.timestamp, *cols)
            .filter(*conds)
            .order_by(Telemetry.timestamp.asc())
            .all()
        )
    else:
        span = int((last_ts - first_ts).total_seconds())
        bucket_seconds = max(1, math.ceil((span + 1) / TELEMETRY_MAX_POINTS))
        bucket = func.timestampdiff(literal_column("SECOND"), first_ts, Telemetry.timestamp).op("DIV")(bucket_seconds)
        rows = (
            db.query(func.min(Telemetry.timestamp), *(func.avg(c) for c in cols))
            .filter(*conds)
            .group_by(bucket)
            .order_by(bucket)
            .all()
        )
    return [(ts.isoformat(), *vals) for ts, *vals in rows]


# ==========================
# GET /api/analytics/auv-status
# SPPI-41 getAuvStatusAnalytics
# ==========================
# Catatan: masih 500 baris PERTAMA (seperti telemetry dulu) — endpoint ini
# belum dipakai frontend; perbaiki dengan pola _telemetry_series kalau dipakai
# (heading berupa teks, tidak bisa dirata-rata).
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