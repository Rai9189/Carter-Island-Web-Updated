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
from datetime import datetime, timedelta, timezone

from database.connection import SessionLocal
from database.models import Detection, MonitoringSession, SessionStatus, Telemetry, AUVStatus
from database.crud.fish_counts import recompute_fish_counts
from core.cuid import generate_cuid

logger = logging.getLogger("carter-backend")

# Telemetri/AUVStatus lebih tua dari ini dianggap basi untuk konteks deteksi
# (health check menyimpan tiap 5 detik → 3x interval sampling).
CONTEXT_MAX_AGE_SECONDS = 15

# Supaya "tidak ada misi aktif" tidak memenuhi log tiap interval simpan
_warned_no_session = False


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
        session_id        : ID sesi monitoring — jika None pakai sesi RUNNING;
                            tanpa sesi RUNNING deteksi TIDAK disimpan
        telemetry_id      : FK ke telemetries (opsional)
        depth_at_detection: Kedalaman ROV saat deteksi (opsional)
        Kalau telemetry_id & depth_at_detection sama-sama None, diisi dari
        data segar (≤ CONTEXT_MAX_AGE_SECONDS) misi yang sama — lihat
        _recent_context().

    Returns:
        True jika berhasil disimpan, False jika gagal / tidak ada misi aktif
    """
    global _warned_no_session
    if not detections:
        return False

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Pakai session_id dari parameter; jika tidak ada, ambil session aktif
        if session_id:
            active_session_id = session_id
        else:
            active = (
                db.query(MonitoringSession.id)
                .filter(MonitoringSession.status == SessionStatus.RUNNING)
                .order_by(MonitoringSession.start_time.desc())
                .first()
            )
            if active is None:
                if not _warned_no_session:
                    logger.warning(
                        "Deteksi tidak disimpan: tidak ada misi Running "
                        "(pesan ini muncul sekali sampai ada misi lagi)"
                    )
                    _warned_no_session = True
                return False
            active_session_id = active.id
        _warned_no_session = False

        if telemetry_id is None and depth_at_detection is None:
            telemetry_id, depth_at_detection = _recent_context(db, active_session_id, now)

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


def _recent_context(db, session_id: str, now: datetime) -> Tuple[Optional[str], Optional[float]]:
    """
    (telemetry_id, depth) dari data misi yang sama yang masih segar:
    Telemetry terbaru → id + depth-nya; kalau tidak ada, AUVStatus terbaru →
    depth saja; kalau tidak ada keduanya → (None, None). Data basi tidak dipakai.
    """
    # Kolom DATETIME menyimpan UTC tanpa zona waktu
    since = (now - timedelta(seconds=CONTEXT_MAX_AGE_SECONDS)).replace(tzinfo=None)

    tel = (
        db.query(Telemetry.id, Telemetry.depth)
        .filter(Telemetry.session_id == session_id, Telemetry.timestamp >= since)
        .order_by(Telemetry.timestamp.desc())
        .first()
    )
    if tel is not None:
        return tel.id, tel.depth

    auv_depth = (
        db.query(AUVStatus.depth)
        .filter(AUVStatus.session_id == session_id, AUVStatus.timestamp >= since)
        .order_by(AUVStatus.timestamp.desc())
        .limit(1)
        .scalar()
    )
    return None, auv_depth
