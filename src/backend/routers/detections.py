"""
Router detections — menggantikan:
  - src/app/api/detections/route.ts        (GET list, POST)
  - src/app/api/detections/stats/route.ts  (GET stats)

POST deteksi tidak lagi lewat HTTP — YOLO simpan langsung
via database/crud/detections.py. Router ini hanya untuk
membaca data yang sudah tersimpan.

Perubahan dari versi lama:
  - Model FishDetection + DetectionDetail → Detection
  - Filter class_name langsung di Detection.species_name
  - Stats dihitung dari Detection langsung (tidak perlu join DetectionDetail)
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.connection import get_db
from database.models import Detection
from core.dependencies import get_current_user

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/detections", tags=["Detections"])


# ==========================
# GET /api/detections — list dengan pagination
# ==========================
@router.get("")
def get_detections(
    page: int = 1,
    limit: int = 20,
    session_id: Optional[str] = None,
    species_name: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET list deteksi dengan pagination + filter.
    """
    skip = (page - 1) * limit
    query = db.query(Detection)

    if session_id:
        query = query.filter(Detection.session_id == session_id)

    if species_name:
        query = query.filter(Detection.species_name.contains(species_name))

    total = query.count()
    detections = (
        query.order_by(Detection.detected_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": [_format_detection(d) for d in detections],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": (total + limit - 1) // limit,
        },
    }


# ==========================
# GET /api/detections/stats
# ==========================
@router.get("/stats")
def get_detection_stats(
    session_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET statistik deteksi — total, per spesies, avg confidence.
    """
    query = db.query(Detection)

    if session_id:
        query = query.filter(Detection.session_id == session_id)

    if start_date:
        query = query.filter(
            Detection.detected_at >= datetime.fromisoformat(start_date)
        )
    if end_date:
        query = query.filter(
            Detection.detected_at <= datetime.fromisoformat(end_date)
        )

    total_detections = query.count()

    # Avg confidence keseluruhan
    avg_conf = db.query(
        func.avg(Detection.confidence)
    ).filter(
        *([Detection.session_id == session_id] if session_id else [])
    ).scalar() or 0.0

    # Groupby species
    by_species = (
        query.with_entities(
            Detection.species_name,
            func.count(Detection.species_name).label("count"),
            func.avg(Detection.confidence).label("avg_conf"),
        )
        .group_by(Detection.species_name)
        .order_by(func.count(Detection.species_name).desc())
        .all()
    )

    # Recent 10 deteksi
    recent = (
        query.order_by(Detection.detected_at.desc())
        .limit(10)
        .all()
    )

    return {
        "success": True,
        "data": {
            "totalDetections": total_detections,
            "averageConfidence": round(float(avg_conf), 4),
            "detectionsBySpecies": [
                {
                    "speciesName": row.species_name,
                    "count": row.count,
                    "avgConfidence": round(float(row.avg_conf), 4),
                }
                for row in by_species
            ],
            "recentDetections": [_format_detection(d) for d in recent],
        },
    }


# ==========================
# GET /api/detections/stats/by-session
# ==========================
@router.get("/stats/by-session")
def get_detection_stats_by_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET distribusi persentase spesies ikan dalam satu sesi survei.
    Digunakan oleh halaman Analytics untuk chart Species Distribution.
    SPPI-36 getDetectionStatsBySession.
    """
    detections = (
        db.query(Detection)
        .filter(Detection.session_id == session_id)
        .all()
    )

    total = len(detections)
    if total == 0:
        return {"success": True, "data": {"total": 0, "distribution": []}}

    # Hitung per spesies
    species_count: dict = {}
    for d in detections:
        species_count[d.species_name] = species_count.get(d.species_name, 0) + 1

    distribution = [
        {
            "speciesName": sp,
            "count": cnt,
            "percentage": round(cnt / total * 100, 1),
        }
        for sp, cnt in sorted(species_count.items(), key=lambda x: -x[1])
    ]

    return {
        "success": True,
        "data": {
            "sessionId": session_id,
            "total": total,
            "distribution": distribution,
        },
    }


# ==========================
# Helper
# ==========================
def _format_detection(d: Detection) -> dict:
    return {
        "id": d.id,
        "sessionId": d.session_id,
        "telemetryId": d.telemetry_id,
        "speciesName": d.species_name,
        "confidence": d.confidence,
        "depthAtDetection": d.depth_at_detection,
        "frameNumber": d.frame_number,
        "detectedAt": d.detected_at.isoformat(),
        "createdAt": d.created_at.isoformat(),
    }