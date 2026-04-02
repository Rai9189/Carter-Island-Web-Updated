"""
Router detections — menggantikan:
  - src/app/api/detections/route.ts        (GET list, POST)
  - src/app/api/detections/stats/route.ts  (GET stats)

POST deteksi tidak lagi lewat HTTP — YOLO simpan langsung
via database/crud/detections.py. Router ini hanya untuk
membaca data yang sudah tersimpan.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.connection import get_db
from database.models import FishDetection, DetectionDetail
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
    class_name: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET list deteksi dengan pagination + filter.
    Port dari src/app/api/detections/route.ts GET
    """
    skip = (page - 1) * limit
    query = db.query(FishDetection)

    if session_id:
        query = query.filter(FishDetection.session_id == session_id)

    if class_name:
        query = query.filter(
            FishDetection.detection_details.any(
                DetectionDetail.class_name.contains(class_name)
            )
        )

    total = query.count()
    detections = (
        query.order_by(FishDetection.timestamp.desc())
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
    GET statistik deteksi — total, per class, avg confidence.
    Port dari src/app/api/detections/stats/route.ts
    """
    from datetime import datetime

    # Build filter untuk FishDetection
    det_query = db.query(FishDetection)
    detail_filter = []

    if session_id:
        det_query = det_query.filter(FishDetection.session_id == session_id)
        detail_filter.append(DetectionDetail.detection.has(
            FishDetection.session_id == session_id
        ))

    if start_date or end_date:
        if start_date:
            dt_start = datetime.fromisoformat(start_date)
            det_query = det_query.filter(FishDetection.timestamp >= dt_start)
            detail_filter.append(DetectionDetail.detection.has(
                FishDetection.timestamp >= dt_start
            ))
        if end_date:
            dt_end = datetime.fromisoformat(end_date)
            det_query = det_query.filter(FishDetection.timestamp <= dt_end)
            detail_filter.append(DetectionDetail.detection.has(
                FishDetection.timestamp <= dt_end
            ))

    # Total deteksi dan jumlah ikan
    total_detections = det_query.count()
    total_fish = db.query(func.sum(FishDetection.fish_count)).scalar() or 0

    # Detail query dengan filter
    detail_query = db.query(DetectionDetail)
    for f in detail_filter:
        detail_query = detail_query.filter(f)

    # Avg confidence keseluruhan
    avg_conf = db.query(func.avg(DetectionDetail.confidence)).scalar() or 0.0

    # Groupby class
    by_class = (
        db.query(
            DetectionDetail.class_name,
            func.count(DetectionDetail.class_name).label("count"),
            func.avg(DetectionDetail.confidence).label("avg_conf"),
        )
        .group_by(DetectionDetail.class_name)
        .order_by(func.count(DetectionDetail.class_name).desc())
        .all()
    )

    # Recent 10 deteksi
    recent = (
        det_query
        .order_by(FishDetection.timestamp.desc())
        .limit(10)
        .all()
    )

    return {
        "success": True,
        "data": {
            "totalDetections": total_detections,
            "totalFishCount": int(total_fish),
            "averageConfidence": round(float(avg_conf), 4),
            "detectionsByClass": [
                {
                    "className": row.class_name,
                    "count": row.count,
                    "avgConfidence": round(float(row.avg_conf), 4),
                }
                for row in by_class
            ],
            "recentDetections": [
                {
                    "id": d.id,
                    "timestamp": d.timestamp.isoformat(),
                    "fishCount": d.fish_count,
                    "classes": [det.class_name for det in d.detection_details],
                }
                for d in recent
            ],
        },
    }


# ==========================
# Helper
# ==========================
def _format_detection(d: FishDetection) -> dict:
    return {
        "id": d.id,
        "sessionId": d.session_id,
        "timestamp": d.timestamp.isoformat(),
        "fishCount": d.fish_count,
        "frameNumber": d.frame_number,
        "imageUrl": d.image_url,
        "detectionDetails": [
            {
                "id": det.id,
                "className": det.class_name,
                "confidence": det.confidence,
                "boundingBox": {
                    "x1": det.bbox_x1,
                    "y1": det.bbox_y1,
                    "x2": det.bbox_x2,
                    "y2": det.bbox_y2,
                },
            }
            for det in d.detection_details
        ],
    }