"""
CRUD operations untuk detections.
Menggantikan HTTP call ke Next.js API /api/detections.

Sebelumnya:
    await http_client.post(f"{API_BASE_URL}/api/detections", json=payload)

Sekarang:
    await save_detection_to_db(detections, frame_number)
    → langsung tulis ke MySQL via SQLAlchemy

Perubahan dari versi lama:
    - Model FishDetection + DetectionDetail → Detection (sesuai models.py baru)
    - Satu bounding box = satu record Detection
    - Tambah field species_name, depth_at_detection
    - session_id sekarang FK ke monitoring_sessions
"""
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone

from database.connection import SessionLocal
from database.models import Detection
from core.cuid import generate_cuid
from config import streaming_session_id

logger = logging.getLogger("carter-backend")


async def save_detection_to_db(
    detections: List[Tuple[int, int, int, int, float, str]],
    frame_number: Optional[int] = None,
    session_id: Optional[str] = None,
    telemetry_id: Optional[str] = None,
    depth_at_detection: Optional[float] = None,
) -> bool:
    """
    Simpan hasil deteksi YOLO langsung ke MySQL via SQLAlchemy.
    Setiap bounding box disimpan sebagai satu record Detection.

    Args:
        detections        : List of (x1, y1, x2, y2, confidence, class_name)
                            dari run_inference() di yolo_detector.py
        frame_number      : Nomor frame saat deteksi (opsional)
        session_id        : ID sesi monitoring — jika None pakai streaming_session_id
        telemetry_id      : FK ke telemetries untuk konteks kedalaman (opsional)
        depth_at_detection: Kedalaman ROV saat deteksi terjadi (opsional)

    Returns:
        True jika berhasil disimpan, False jika gagal
    """
    if not detections:
        return False

    # Pakai session_id dari parameter, fallback ke streaming_session_id
    active_session_id = session_id or streaming_session_id

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Setiap deteksi = satu record Detection
        for (x1, y1, x2, y2, conf, class_name) in detections:
            detection = Detection(
                id=generate_cuid(),
                session_id=active_session_id,
                telemetry_id=telemetry_id,
                species_name=class_name,
                confidence=float(conf),
                depth_at_detection=depth_at_detection,
                frame_number=frame_number,
                detected_at=now,
                created_at=now,
            )
            db.add(detection)

        db.commit()
        logger.info(
            f"Saved {len(detections)} detections to DB "
            f"(frame {frame_number}, session {active_session_id[:8]}...)"
        )
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving detections to DB: {e}")
        return False
    finally:
        db.close()