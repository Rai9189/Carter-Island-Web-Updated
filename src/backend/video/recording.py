import os
import cv2
import logging
from typing import Optional, Dict
from datetime import datetime
import pytz
from config import (
    RECORDINGS_DIR,
    RESIZE_WIDTH,
    RESIZE_HEIGHT,
    streaming_session_id
)
from database.crud.recordings import save_recording_to_db  # GANTI: tidak pakai httpx lagi

# Jakarta timezone
JAKARTA_TZ = pytz.timezone('Asia/Jakarta')

logger = logging.getLogger("carter-backend")

# Active recordings
active_recordings: Dict[str, dict] = {}


def initialize_recordings_dir():
    logger.info(f"Recordings will be stored in system temp directory: {RECORDINGS_DIR}")


def create_video_writer(recording_id: str) -> Optional[cv2.VideoWriter]:
    try:
        filename = f"recording_{recording_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        filepath = os.path.join(RECORDINGS_DIR, filename)

        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        writer = cv2.VideoWriter(
            filepath,
            fourcc,
            10.0,
            (RESIZE_WIDTH, RESIZE_HEIGHT)
        )

        if not writer.isOpened():
            logger.error(f"Failed to open video writer for {filepath}")
            return None

        logger.info(f"Created video writer: {filepath}")
        return writer

    except Exception as e:
        logger.error(f"Error creating video writer: {e}")
        return None


async def start_recording(client_id: str, detection_track) -> Optional[str]:
    if client_id in active_recordings:
        logger.warning(f"Client {client_id} is already recording")
        return None

    try:
        from video.detection_track import get_fps

        recording_id = f"{client_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        filename = f"recording_{recording_id}.webm"
        filepath = os.path.join(RECORDINGS_DIR, filename)

        actual_fps = get_fps()
        if actual_fps <= 0:
            actual_fps = 10.0

        logger.info(f"Recording at {actual_fps:.1f} FPS (full stream rate)")

        fourcc_options = [
            cv2.VideoWriter.fourcc(*'VP80'),
            cv2.VideoWriter.fourcc(*'VP90'),
        ]

        writer = None
        for fourcc in fourcc_options:
            writer = cv2.VideoWriter(
                filepath,
                fourcc,
                actual_fps,
                (RESIZE_WIDTH, RESIZE_HEIGHT)
            )
            if writer.isOpened():
                logger.info(f"Using codec: {fourcc} at {actual_fps:.1f} FPS")
                break
            writer.release()
            writer = None

        if writer is None or not writer.isOpened():
            logger.error(f"Failed to open video writer for {filepath}")
            return None

        detection_track.start_recording(writer)

        active_recordings[client_id] = {
            "recording_id": recording_id,
            "filename": filename,
            "filepath": filepath,
            "writer": writer,
            "start_time": datetime.now(JAKARTA_TZ),
            "session_id": streaming_session_id
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

        # Hitung ukuran dan durasi
        file_size = os.path.getsize(filepath)
        end_time = datetime.now(JAKARTA_TZ)
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

        # GANTI: simpan langsung via SQLAlchemy, tidak lewat HTTP ke Next.js
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
            logger.info(f"Recording saved to DB with id: {db_id}")
        else:
            logger.warning(f"Failed to save recording to DB")

        return recording_data

    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        return None


def is_recording(client_id: str) -> bool:
    return client_id in active_recordings


def get_recording_info(client_id: str) -> Optional[dict]:
    return active_recordings.get(client_id)


def cleanup_all_recordings():
    for client_id in list(active_recordings.keys()):
        recording_info = active_recordings.pop(client_id)
        try:
            recording_info["writer"].release()
            logger.info(f"Cleaned up recording for client {client_id}")
        except Exception as e:
            logger.error(f"Error cleaning up recording for {client_id}: {e}")