"""
Router recordings — menggantikan:
  - src/app/api/recordings/route.ts      (GET list, DELETE)
  - src/app/api/recordings/[id]/route.ts (GET by id, DELETE by id)

Digabung dengan endpoint video stream/download yang sudah ada
di api/routes.py:
  - GET /api/video/stream/{filename}
  - GET /api/video/download/{filename}
"""
import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Recording
from core.dependencies import get_current_user
from config import RECORDINGS_DIR

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/recordings", tags=["Recordings"])


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
    """
    GET list recordings dengan pagination.
    Port dari src/app/api/recordings/route.ts GET
    """
    skip = (page - 1) * limit
    query = db.query(Recording)

    if session_id:
        query = query.filter(Recording.session_id == session_id)

    total = query.count()
    recordings = (
        query.order_by(Recording.start_time.desc())
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
    """
    GET single recording by ID.
    Port dari src/app/api/recordings/[id]/route.ts GET
    """
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
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
    _: dict = Depends(get_current_user),
):
    """
    DELETE recording by ID (hapus dari DB saja, file fisik tetap ada).
    Port dari src/app/api/recordings/[id]/route.ts DELETE
    """
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
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
    """
    Stream video file untuk playback di browser.
    Dipindahkan dari api/routes.py /api/video/stream/{filename}
    """
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
    """
    Download video file.
    Dipindahkan dari api/routes.py /api/video/download/{filename}
    """
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
def _format_recording(r: Recording) -> dict:
    return {
        "id": r.id,
        "sessionId": r.session_id,
        "filename": r.filename,
        "filepath": r.filepath,
        "fileSize": str(r.file_size),  # BigInt → string untuk JSON
        "duration": r.duration,
        "startTime": r.start_time.isoformat(),
        "endTime": r.end_time.isoformat(),
        "createdAt": r.created_at.isoformat(),
        "updatedAt": r.updated_at.isoformat(),
    }