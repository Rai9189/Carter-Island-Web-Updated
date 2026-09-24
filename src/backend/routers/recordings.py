"""
Router recordings — menggantikan:
  - src/app/api/recordings/route.ts      (GET list, DELETE)
  - src/app/api/recordings/[id]/route.ts (GET by id, DELETE by id)

Perubahan dari versi lama:
  - Model Recording → VideoPath (sesuai models.py baru)
  - Field filename → file_name
  - Field start_time/end_time dihapus (ada di monitoring_sessions)
  - Urutan sort pakai created_at
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import VideoPath, MonitoringSession, SessionStatus
from core.dependencies import get_current_user, require_admin
from config import RECORDINGS_DIR

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/recordings", tags=["Recordings"])


# ==========================
# POST /api/recordings/save — selesaikan sesi & simpan info misi
# ==========================
@router.post("/save")
def save_recording_session(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Dipanggil frontend setelah user mengisi form simpan recording.
    Menandai sesi sebagai Completed dan update nama lokasi/misi.

    Payload:
        sessionId   : str — ID sesi aktif (wajib)
        missionName : str — nama misi (dipakai sebagai location_name)
        location    : str — lokasi survei (fallback jika missionName kosong)
        description : str — deskripsi opsional (tidak disimpan ke DB saat ini)
        clientId    : str — opsional, untuk referensi logging
    """
    session_id = body.get("sessionId")
    mission_name = (body.get("missionName") or "").strip()
    location = (body.get("location") or "").strip()

    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId wajib diisi")

    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan")

    if session.status != SessionStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Session sudah {session.status.value}, tidak bisa diubah lagi"
        )

    now = datetime.now(timezone.utc)
    label = mission_name or location
    if label:
        session.location_name = label
    session.status = SessionStatus.COMPLETED
    session.end_time = now
    session.updated_at = now

    db.commit()

    logger.info(f"Session {session_id} → Completed via save_recording (mission: {label})")
    return {"success": True, "message": "Recording berhasil disimpan"}


# ==========================
# GET /api/recordings — list dengan pagination
# ==========================
@router.get("")
def get_recordings(
    page: int = 1,
    limit: int = 20,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    limit = min(max(limit, 1), 500)
    page = max(page, 1)
    skip = (page - 1) * limit
    query = db.query(VideoPath)

    if session_id:
        query = query.filter(VideoPath.session_id == session_id)

    total = query.count()
    recordings = (
        query.order_by(VideoPath.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": [_format_recording(r) for r in recordings],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": (total + limit - 1) // limit,
        },
    }


# ==========================
# GET /api/recordings/{recording_id}
# ==========================
@router.get("/{recording_id}")
def get_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    recording = db.query(VideoPath).filter(VideoPath.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording tidak ditemukan")

    return {"success": True, "data": _format_recording(recording)}


# ==========================
# DELETE /api/recordings/{recording_id}
# ==========================
@router.delete("/{recording_id}")
def delete_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    recording = db.query(VideoPath).filter(VideoPath.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording tidak ditemukan")

    db.delete(recording)
    db.commit()

    return {"success": True, "message": "Recording berhasil dihapus"}


# ==========================
# GET /api/recordings/stream/{filename}
# ==========================
@router.get("/stream/{filename}")
def stream_video(
    filename: str,
    _: dict = Depends(get_current_user),
):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nama file tidak valid")

    filepath = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Video tidak ditemukan")

    media_type = "video/webm" if filename.endswith(".webm") else "video/mp4"
    return FileResponse(filepath, media_type=media_type, filename=filename)


# ==========================
# GET /api/recordings/download/{filename}
# ==========================
@router.get("/download/{filename}")
def download_video(
    filename: str,
    _: dict = Depends(get_current_user),
):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nama file tidak valid")

    filepath = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Video tidak ditemukan")

    media_type = "video/webm" if filename.endswith(".webm") else "video/mp4"
    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ==========================
# Helper
# ==========================
def _format_recording(r: VideoPath) -> dict:
    return {
        "id": r.id,
        "sessionId": r.session_id,
        "fileName": r.file_name,
        "filePath": r.file_path,
        "fileSize": r.file_size,
        "format": r.format,
        "duration": r.duration,
        "createdAt": r.created_at.isoformat(),
        "updatedAt": r.updated_at.isoformat(),
    }