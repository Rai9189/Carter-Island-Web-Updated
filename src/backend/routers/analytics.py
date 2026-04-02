"""
Router analytics — menggantikan:
  - src/app/api/analytics/detections/route.ts   (GET)
  - src/app/api/analytics/telemetry/route.ts    (GET)
  - src/app/api/analytics/auv-status/route.ts   (GET)
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.connection import get_db
from database.models import FishDetection, DetectionDetail, Telemetry, AUVStatus
from core.dependencies import get_current_user

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


# ==========================
# GET /api/analytics/detections
# ==========================
@router.get("/detections")
def get_detection_analytics(
    hours: int = 24,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET analitik deteksi ikan.
    Port dari src/app/api/analytics/detections/route.ts
    """
    start_time = datetime.utcnow() - timedelta(hours=hours)

    detections = (
        db.query(FishDetection)
        .filter(FishDetection.timestamp >= start_time)
        .order_by(FishDetection.timestamp.asc())
        .all()
    )

    # Agregasi per jam
    hourly: dict = {}
    species: dict = {}

    for d in detections:
        hour = d.timestamp.replace(minute=0, second=0, microsecond=0)
        hour_key = hour.isoformat()
        if hour_key not in hourly:
            hourly[hour_key] = {"count": 0, "totalFish": 0}
        hourly[hour_key]["count"] += 1
        hourly[hour_key]["totalFish"] += d.fish_count

        for det in d.detection_details:
            species[det.class_name] = species.get(det.class_name, 0) + 1

    # Stats keseluruhan
    total_fish = sum(d.fish_count for d in detections)
    avg_conf = 0.0
    all_details = [det for d in detections for det in d.detection_details]
    if all_details:
        avg_conf = sum(det.confidence for det in all_details) / len(all_details)

    return {
        "success": True,
        "data": {
            "summary": {
                "totalDetections": len(detections),
                "totalFish": total_fish,
                "avgConfidence": round(avg_conf, 4),
                "uniqueSpecies": len(species),
            },
            "timeSeries": [
                {
                    "time": time,
                    "detections": data["count"],
                    "fishCount": data["totalFish"],
                }
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
# ==========================
@router.get("/telemetry")
def get_telemetry_analytics(
    hours: int = 24,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET analitik telemetri — battery, attitude, compass, health.
    Port dari src/app/api/analytics/telemetry/route.ts
    """
    start_time = datetime.utcnow() - timedelta(hours=hours)

    telemetry = (
        db.query(Telemetry)
        .filter(Telemetry.timestamp >= start_time)
        .order_by(Telemetry.timestamp.asc())
        .limit(288)
        .all()
    )

    latest = telemetry[-1] if telemetry else None
    avg_battery = (
        sum(t.remaining_percent for t in telemetry) / len(telemetry)
        if telemetry else 0
    )

    return {
        "success": True,
        "data": {
            "summary": {
                "currentBattery": round(latest.remaining_percent, 1) if latest else "N/A",
                "avgBattery": round(avg_battery, 1),
                "currentVoltage": round(latest.voltage_v, 2) if latest else "N/A",
                "dataPoints": len(telemetry),
            },
            "battery": [
                {
                    "time": t.timestamp.isoformat(),
                    "voltage": round(t.voltage_v, 2),
                    "remaining": round(t.remaining_percent, 1),
                }
                for t in telemetry
            ],
            "attitude": [
                {
                    "time": t.timestamp.isoformat(),
                    "roll": round(t.roll_deg, 1),
                    "pitch": round(t.pitch_deg, 1),
                    "yaw": round(t.yaw_deg, 1),
                }
                for t in telemetry
            ],
            "compass": [
                {
                    "time": t.timestamp.isoformat(),
                    "heading": round(t.heading_deg, 1),
                }
                for t in telemetry
            ],
            "health": [
                {
                    "time": t.timestamp.isoformat(),
                    "gyro": 1 if t.gyro_cal else 0,
                    "accel": 1 if t.accel_cal else 0,
                    "mag": 1 if t.mag_cal else 0,
                }
                for t in telemetry
            ],
        },
    }


# ==========================
# GET /api/analytics/auv-status
# ==========================
@router.get("/auv-status")
def get_auv_status_analytics(
    hours: int = 24,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET analitik AUV status — uptime, connection distribution.
    Port dari src/app/api/analytics/auv-status/route.ts
    """
    start_time = datetime.utcnow() - timedelta(hours=hours)

    status_data = (
        db.query(AUVStatus)
        .filter(AUVStatus.timestamp >= start_time)
        .order_by(AUVStatus.timestamp.asc())
        .limit(288)
        .all()
    )

    # Distribusi connection strength
    conn_stats: dict = {}
    for s in status_data:
        conn_stats[s.connection_strength] = conn_stats.get(s.connection_strength, 0) + 1

    # Uptime percentage
    online_count = sum(1 for s in status_data if s.is_online)
    uptime_pct = (online_count / len(status_data) * 100) if status_data else 0

    # Avg uptime dalam menit
    avg_uptime_sec = (
        sum(s.uptime_seconds for s in status_data) / len(status_data)
        if status_data else 0
    )

    latest = status_data[-1] if status_data else None

    return {
        "success": True,
        "data": {
            "summary": {
                "uptimePercentage": round(uptime_pct, 1),
                "avgUptimeMinutes": int(avg_uptime_sec // 60),
                "totalStatusChecks": len(status_data),
                "currentlyOnline": latest.is_online if latest else False,
            },
            "statusHistory": [
                {
                    "time": s.timestamp.isoformat(),
                    "online": 1 if s.is_online else 0,
                    "uptime": s.uptime_seconds,
                    "connection": s.connection_strength,
                }
                for s in status_data
            ],
            "uptimeHistory": [
                {
                    "time": s.timestamp.isoformat(),
                    "uptime": s.uptime_seconds // 60,
                }
                for s in status_data
            ],
            "connectionDistribution": [
                {"status": status, "count": count}
                for status, count in conn_stats.items()
            ],
        },
    }