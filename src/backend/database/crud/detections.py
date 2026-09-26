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
import asyncio
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone

from database.connection import SessionLocal
from database.models import Detection
from database.crud.fish_counts import recompute_fish_counts
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
    Versi async untuk dipanggil dari loop video: kerja DB (termasuk
    recompute_fish_counts yang makin berat seiring misi) dijalankan di thread
    agar tidak memblokir event loop (frame video, API, scheduler).
    """
    return await asyncio.to_thread(
        _save_detections_sync,
        detections, frame_number, session_id, telemetry_id, depth_at_detection,
    )


def _save_detections_sync(
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

    # Pakai session_id dari parameter; jika tidak ada, ambil session aktif dari DB
    if session_id:
        active_session_id = session_id
    else:
        try:
            from database.connection import SessionLocal
            from database.models import MonitoringSession, SessionStatus
            _db = SessionLocal()
            try:
                _s = _db.query(MonitoringSession).filter(
                    MonitoringSession.status == SessionStatus.RUNNING
                ).order_by(MonitoringSession.start_time.desc()).first()
                active_session_id = _s.id if _s else streaming_session_id
            finally:
                _db.close()
        except Exception:
            active_session_id = streaming_session_id

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

        # Deteksi sudah aman tersimpan; gagal agregasi tidak membatalkannya
        try:
            recompute_fish_counts(db, active_session_id)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating fish_counts: {e}")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving detections to DB: {e}")
        return False
    finally:
        db.close()