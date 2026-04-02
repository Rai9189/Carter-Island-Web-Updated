"""
CRUD operations untuk recordings.
Menggantikan HTTP call ke Next.js API /api/recordings.

Sebelumnya (video/recording.py):
    await http_client.post(f"{API_BASE_URL}/api/recordings", json={...})

Sekarang:
    await save_recording_to_db(recording_data)
    → langsung tulis ke MySQL via SQLAlchemy
"""
import logging
from datetime import datetime
from typing import Optional

from database.connection import SessionLocal
from database.models import Recording
from core.cuid import generate_cuid

logger = logging.getLogger("carter-backend")


async def save_recording_to_db(
    session_id: str,
    filename: str,
    filepath: str,
    file_size: int,
    duration: float,
    start_time: datetime,
    end_time: datetime,
) -> Optional[str]:
    """
    Simpan metadata recording langsung ke MySQL via SQLAlchemy.
    Menggantikan: http_client.post(f"{API_BASE_URL}/api/recordings", ...)

    Args:
        session_id: ID sesi streaming
        filename: Nama file video (contoh: recording_abc123.webm)
        filepath: Path lengkap ke file video
        file_size: Ukuran file dalam bytes
        duration: Durasi video dalam detik
        start_time: Waktu mulai recording
        end_time: Waktu selesai recording

    Returns:
        ID recording yang baru dibuat, atau None jika gagal
    """
    db = SessionLocal()
    try:
        recording_id = generate_cuid()
        now = datetime.utcnow()

        recording = Recording(
            id=recording_id,
            session_id=session_id,
            filename=filename,
            filepath=filepath,
            file_size=file_size,
            duration=duration,
            start_time=start_time,
            end_time=end_time,
            created_at=now,
            updated_at=now,
        )

        db.add(recording)
        db.commit()

        logger.info(
            f"Saved recording to DB: {filename} "
            f"({duration:.1f}s, {file_size/1024/1024:.2f}MB)"
        )
        return recording_id

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving recording to DB: {e}")
        return None
    finally:
        db.close()