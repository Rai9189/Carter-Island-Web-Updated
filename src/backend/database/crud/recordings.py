"""
CRUD operations untuk video_paths.
Menggantikan HTTP call ke Next.js API /api/recordings.

Sebelumnya (video/recording.py):
    await http_client.post(f"{API_BASE_URL}/api/recordings", json={...})

Sekarang:
    await save_recording_to_db(recording_data)
    → langsung tulis ke MySQL via SQLAlchemy

Perubahan dari versi lama:
    - Model Recording → VideoPath (sesuai models.py baru)
    - Field filename → file_name
    - Field duration → tetap (opsional di VideoPath)
    - Tambah field format (mp4/webm)
    - session_id sekarang FK ke monitoring_sessions
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from database.connection import SessionLocal
from database.models import VideoPath
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
        session_id : ID sesi monitoring (FK ke monitoring_sessions)
        filename   : Nama file video (contoh: recording_abc123.webm)
        filepath   : Path lengkap ke file video
        file_size  : Ukuran file dalam bytes
        duration   : Durasi video dalam detik
        start_time : Waktu mulai recording (tidak dipakai di VideoPath,
                     disimpan di monitoring_sessions.start_time)
        end_time   : Waktu selesai recording (tidak dipakai di VideoPath)

    Returns:
        ID VideoPath yang baru dibuat, atau None jika gagal
    """
    # Kerja DB di thread agar tidak memblokir event loop
    return await asyncio.to_thread(
        _save_recording_sync, session_id, filename, filepath, file_size, duration,
    )


def _save_recording_sync(
    session_id: str, filename: str, filepath: str, file_size: int, duration: float,
) -> Optional[str]:
    db = SessionLocal()
    try:
        video_path_id = generate_cuid()
        now = datetime.now(timezone.utc)

        # Deteksi format dari ekstensi file
        fmt = "webm" if filename.endswith(".webm") else "mp4"

        video_path = VideoPath(
            id=video_path_id,
            session_id=session_id,
            file_name=filename,
            file_path=filepath,
            file_size=file_size,
            format=fmt,
            duration=duration,
            created_at=now,
            updated_at=now,
        )

        db.add(video_path)
        db.commit()

        logger.info(
            f"Saved video_path to DB: {filename} "
            f"({duration:.1f}s, {file_size/1024/1024:.2f}MB)"
        )
        return video_path_id

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving video_path to DB: {e}")
        return None
    finally:
        db.close()