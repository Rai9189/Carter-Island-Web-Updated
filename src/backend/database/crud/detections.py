"""
CRUD operations untuk fish detections.
Menggantikan HTTP call ke Next.js API /api/detections.

Sebelumnya (database/detections.py):
    await http_client.post(f"{API_BASE_URL}/api/detections", json=payload)

Sekarang:
    await save_detection_to_db(detections, frame_number)
    → langsung tulis ke MySQL via SQLAlchemy
"""
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone

from database.connection import SessionLocal
from database.models import FishDetection, DetectionDetail
from core.cuid import generate_cuid
from config import streaming_session_id

logger = logging.getLogger("carter-backend")


async def save_detection_to_db(
    detections: List[Tuple[int, int, int, int, float, str]],
    frame_number: Optional[int] = None,
) -> bool:
    """
    Simpan hasil deteksi YOLO langsung ke MySQL via SQLAlchemy.
    Menggantikan: http_client.post(f"{API_BASE_URL}/api/detections", ...)

    Args:
        detections: List of (x1, y1, x2, y2, confidence, class_name)
                    dari run_inference() di yolo_detector.py
        frame_number: Nomor frame saat deteksi (opsional)

    Returns:
        True jika berhasil disimpan, False jika gagal
    """
    if not detections:
        return False

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Buat record FishDetection utama
        detection = FishDetection(
            id=generate_cuid(),
            session_id=streaming_session_id,
            timestamp=now,
            fish_count=len(detections),
            frame_number=frame_number,
            image_url=None,
            created_at=now,
            updated_at=now,
        )
        db.add(detection)
        db.flush()  # Dapatkan ID tanpa commit dulu

        # Buat record DetectionDetail untuk setiap ikan
        for (x1, y1, x2, y2, conf, class_name) in detections:
            detail = DetectionDetail(
                id=generate_cuid(),
                detection_id=detection.id,
                class_name=class_name,
                confidence=float(conf),
                bbox_x1=float(x1),
                bbox_y1=float(y1),
                bbox_x2=float(x2),
                bbox_y2=float(y2),
                created_at=now,
            )
            db.add(detail)

        db.commit()
        logger.info(
            f"Saved {len(detections)} detections to DB "
            f"(frame {frame_number}, session {streaming_session_id[:8]}...)"
        )
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving detections to DB: {e}")
        return False
    finally:
        db.close()