import asyncio
import os
import logging
from typing import Optional, Dict
from datetime import datetime
import pytz
from config import RECORDINGS_DIR
from database.crud.recordings import save_recording_to_db

# Jakarta timezone
JAKARTA_TZ = pytz.timezone('Asia/Jakarta')

logger = logging.getLogger("carter-backend")

# Active recordings
active_recordings: Dict[str, dict] = {}


class NoActiveMissionError(Exception):
    """Tidak ada misi Running — rekaman ditolak agar video tidak yatim
    (video_paths.session_id wajib merujuk ke misi yang ada)."""


def _active_session_id() -> Optional[str]:
    from database.connection import SessionLocal
    from database.models import MonitoringSession, SessionStatus
    db = SessionLocal()
    try:
        s = db.query(MonitoringSession).filter(
            MonitoringSession.status == SessionStatus.RUNNING
        ).order_by(MonitoringSession.start_time.desc()).first()
        return s.id if s else None
    finally:
        db.close()


async def start_recording(client_id: str, detection_track) -> Optional[str]:
    if client_id in active_recordings:
        logger.warning(f"Client {client_id} is already recording")
        return None

    # Ambil session aktif dari DB (di thread, tidak memblokir event loop)
    try:
        actual_session_id = await asyncio.to_thread(_active_session_id)
    except Exception as _e:
        logger.warning(f"Could not get active session from DB: {_e}")
        return None
    if actual_session_id is None:
        logger.warning(f"Rekaman client {client_id} ditolak: tidak ada misi Running")
        raise NoActiveMissionError()

    try:
        recording_id = f"{client_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        filename = f"recording_{recording_id}.mp4"
        filepath = os.path.join(RECORDINGS_DIR, filename)

        detection_track.start_recording(filepath)

        active_recordings[client_id] = {
            "recording_id": recording_id,
            "filename": filename,
            "filepath": filepath,
            "track": detection_track,
            "start_time": datetime.now(JAKARTA_TZ),
            "session_id": actual_session_id
        }

        logger.info(f"Started recording for client {client_id}: {filename}")
        return recording_id

    except Exception as e:
        logger.error(f"Error starting recording: {e}")
        return None


async def stop_recording(client_id: str) -> Optional[dict]:
    if client_id not in active_recordings:
        logger.warning(f"Client {client_id} is not recording")
        return None

    try:
        recording_info = active_recordings.pop(client_id)
        filepath = recording_info["filepath"]
        end_time = datetime.now(JAKARTA_TZ)

        # Tunggu thread penulis menutup file (di thread lain agar event loop tidak terblokir)
        await asyncio.to_thread(recording_info["track"].stop_recording)

        file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        duration = (end_time - recording_info["start_time"]).total_seconds()

        recording_data = {
            "recording_id": recording_info["recording_id"],
            "filename": recording_info["filename"],
            "filepath": filepath,
            "file_size": file_size,
            "duration": duration,
            "start_time": recording_info["start_time"].isoformat(),
            "end_time": end_time.isoformat(),
            "session_id": recording_info["session_id"]
        }

        logger.info(
            f"Stopped recording for client {client_id}: "
            f"{recording_info['filename']} ({duration:.1f}s, {file_size/1024/1024:.2f}MB)"
        )

        # Simpan langsung via SQLAlchemy ke tabel video_paths
        db_id = await save_recording_to_db(
            session_id=recording_info["session_id"],
            filename=recording_info["filename"],
            filepath=filepath,
            file_size=file_size,
            duration=duration,
            start_time=recording_info["start_time"],
            end_time=end_time,
        )

        if db_id:
            logger.info(f"VideoPath saved to DB with id: {db_id}")
        else:
            logger.warning(f"Failed to save VideoPath to DB")

        return recording_data

    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        return None


def is_recording(client_id: str) -> bool:
    return client_id in active_recordings


def get_recording_info(client_id: str) -> Optional[dict]:
    return active_recordings.get(client_id)


def cleanup_all_recordings():
    """Jaring pengaman saat shutdown: tutup file rekaman yang masih terbuka (tanpa simpan DB)."""
    for client_id in list(active_recordings.keys()):
        recording_info = active_recordings.pop(client_id)
        try:
            recording_info["track"].stop_recording()
            logger.info(f"Cleaned up recording for client {client_id}")
        except Exception as e:
            logger.error(f"Error cleaning up recording for {client_id}: {e}")