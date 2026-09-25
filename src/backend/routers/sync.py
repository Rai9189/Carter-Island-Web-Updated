"""
Router sinkronisasi ROV → Base Station (SPPI 45-47).

Alur "store and forward":
  1. ROV simpan data dulu ke DB lokal (Jetson Orin)
  2. Scheduler cek koneksi ke Base Station tiap X detik
  3. Jika connect, ROV kirim data yang belum tersync (is_synced=False)
  4. Base Station terima dan simpan ke DB-nya sendiri
  5. ROV tandai data tersebut is_synced=True

Endpoints (dijalankan di BASE STATION):
  POST /api/sync/sessions     — upsert sesi misi (wajib sebelum data sesi itu diterima)
  POST /api/sync/telemetry    — SPPI-45 syncTelemetry
  POST /api/sync/detections   — SPPI-46 syncDetections
  POST /api/sync/auv-status   — SPPI-47 syncAuvStatus
  GET  /api/sync/status       — cek status sync terakhir
"""
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import (
    Telemetry, Detection, AUVStatus, MonitoringSession, SessionStatus, User, Role,
)
from core.dependencies import get_current_user, verify_sync_token
from core.cuid import generate_cuid
from core.validation import safe_float

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/sync", tags=["Sync"])

# ==========================
# State sync terakhir (in-memory)
# ==========================
_last_sync_info = {
    "sessions": {"last_synced_at": None, "total_received": 0},
    "telemetry": {"last_synced_at": None, "total_received": 0},
    "detections": {"last_synced_at": None, "total_received": 0},
    "auv_status": {"last_synced_at": None, "total_received": 0},
}


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ==========================
# POST /api/sync/sessions
# Sesi misi harus ada di Base Station sebelum datanya (SPPI 45-47) diterima
# ==========================
@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def sync_sessions(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_sync_token),
):
    """
    Buat / perbarui sesi misi dari ROV (upsert, ID sesi sama dengan di ROV).

    Setiap record:
        id            : str — ID sesi di ROV
        location_name : str
        start_time    : str — ISO format
        end_time      : str — ISO format, opsional
        status        : str — Running / Completed / Aborted
        owner_email   : str — pemilik misi di ROV

    User ROV dan Base Station terpisah: pemilik dicocokkan lewat email; kalau
    tidak ada, sesi dicatat atas nama admin pertama Base Station (keputusan
    2026-09-25). Pemilik hanya diisi saat sesi pertama kali dibuat.
    """
    records: List[dict] = body.get("records", [])
    if not records:
        raise HTTPException(status_code=400, detail="records wajib diisi")

    fallback_admin = None
    saved = 0
    skipped_ids = []
    now = datetime.now(timezone.utc)

    for rec in records:
        session_id = rec.get("id")
        try:
            session_status = SessionStatus(rec.get("status"))
        except ValueError:
            session_status = None
        start_time = _parse_dt(rec.get("start_time"))

        if not session_id or not session_status or not start_time:
            logger.warning(f"Skip sesi {session_id}: id/status/start_time tidak valid")
            skipped_ids.append(session_id)
            continue

        session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
        if not session:
            owner = None
            if rec.get("owner_email"):
                owner = db.query(User).filter(User.email == rec["owner_email"]).first()
            if not owner:
                if fallback_admin is None:
                    fallback_admin = (
                        db.query(User).filter(User.role == Role.ADMIN)
                        .order_by(User.created_at.asc()).first()
                    )
                owner = fallback_admin
            if not owner:
                logger.warning(f"Skip sesi {session_id}: tidak ada admin di Base Station")
                skipped_ids.append(session_id)
                continue
            session = MonitoringSession(id=session_id, user_id=owner.id, created_at=now)
            db.add(session)

        session.location_name = rec.get("location_name") or ""
        session.start_time = start_time
        session.end_time = _parse_dt(rec.get("end_time"))
        session.status = session_status
        session.updated_at = now
        saved += 1

    db.commit()

    _last_sync_info["sessions"]["last_synced_at"] = now.isoformat()
    _last_sync_info["sessions"]["total_received"] += saved

    logger.info(f"Sync sessions — saved={saved} skipped={len(skipped_ids)}")

    return {
        "success": True,
        "message": f"{saved} sesi disimpan, {len(skipped_ids)} dilewati (invalid)",
        "saved": saved,
        "skipped": len(skipped_ids),
        "skipped_ids": skipped_ids,
    }


# ==========================
# POST /api/sync/telemetry
# SPPI-45 syncTelemetry
# ==========================
@router.post("/telemetry", status_code=status.HTTP_201_CREATED)
def sync_telemetry(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_sync_token),
):
    """
    Terima batch data telemetri dari ROV dan simpan ke DB Base Station.

    Payload:
        session_id : str  — ID sesi di ROV (harus sudah ada di Base Station)
        records    : list — list data telemetri yang belum tersync

    Setiap record:
        rov_id           : str   — ID asli dari DB ROV (untuk dedup)
        timestamp        : str   — ISO format
        depth            : float
        ph_level         : float
        tds_value        : float
        dissolved_oxygen : float
        water_temp       : float
    """
    session_id = body.get("session_id") or body.get("sessionId")
    records: List[dict] = body.get("records", [])

    if not session_id or not records:
        raise HTTPException(
            status_code=400,
            detail="session_id dan records wajib diisi"
        )

    # Verifikasi sesi ada di Base Station
    session = db.query(MonitoringSession).filter(
        MonitoringSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Sesi {session_id} tidak ditemukan di Base Station. "
                   "Pastikan sesi sudah dibuat terlebih dahulu."
        )

    saved = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for rec in records:
        rov_id = rec.get("rov_id") or rec.get("id")

        # Cek duplikat berdasarkan rov_id (hindari simpan 2x)
        existing = db.query(Telemetry).filter(
            Telemetry.rov_id == rov_id
        ).first() if rov_id else None

        if existing:
            skipped += 1
            continue

        try:
            ts = datetime.fromisoformat(rec.get("timestamp", now.isoformat()))
        except (ValueError, TypeError):
            ts = now

        try:
            telemetry = Telemetry(
                id=generate_cuid(),
                rov_id=rov_id,
                session_id=session_id,
                timestamp=ts,
                depth=safe_float(rec.get("depth"), "depth", default=0.0),
                ph_level=safe_float(rec.get("ph_level"), "ph_level", default=0.0),
                tds_value=safe_float(rec.get("tds_value"), "tds_value", default=0.0),
                dissolved_oxygen=safe_float(rec.get("dissolved_oxygen"), "dissolved_oxygen", default=0.0),
                water_temp=safe_float(rec.get("water_temp"), "water_temp", default=0.0),
                is_synced=True,
                created_at=now,
            )
        except ValueError as e:
            logger.warning(f"Skip record rov_id={rov_id}: {e}")
            skipped += 1
            continue

        db.add(telemetry)
        saved += 1

    db.commit()

    _last_sync_info["telemetry"]["last_synced_at"] = now.isoformat()
    _last_sync_info["telemetry"]["total_received"] += saved

    logger.info(f"Sync telemetry — saved={saved} skipped={skipped} session={session_id[:8]}...")

    return {
        "success": True,
        "message": f"{saved} telemetry records disimpan, {skipped} dilewati (duplikat/invalid)",
        "saved": saved,
        "skipped": skipped,
    }


# ==========================
# POST /api/sync/detections
# SPPI-46 syncDetections
# ==========================
@router.post("/detections", status_code=status.HTTP_201_CREATED)
def sync_detections(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_sync_token),
):
    """
    Terima batch hasil deteksi YOLO dari ROV dan simpan ke DB Base Station.

    Payload:
        session_id : str
        records    : list

    Setiap record:
        rov_id             : str   — ID asli dari DB ROV (untuk dedup)
        telemetry_id       : str   — opsional
        species_name       : str
        confidence         : float
        depth_at_detection : float — opsional
        frame_number       : int   — opsional
        detected_at        : str   — ISO format
    """
    session_id = body.get("session_id") or body.get("sessionId")
    records: List[dict] = body.get("records", [])

    if not session_id or not records:
        raise HTTPException(
            status_code=400,
            detail="session_id dan records wajib diisi"
        )

    session = db.query(MonitoringSession).filter(
        MonitoringSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Sesi {session_id} tidak ditemukan di Base Station."
        )

    saved = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for rec in records:
        rov_id = rec.get("rov_id") or rec.get("id")

        existing = db.query(Detection).filter(
            Detection.rov_id == rov_id
        ).first() if rov_id else None

        if existing:
            skipped += 1
            continue

        try:
            detected_at = datetime.fromisoformat(rec.get("detected_at", now.isoformat()))
        except (ValueError, TypeError):
            detected_at = now

        # telemetry_id dari ROV adalah ID telemetri di DB ROV — cari padanannya
        # di Base Station lewat rov_id; kalau belum tersync, kosongkan (hindari FK error)
        telemetry_id = None
        if rec.get("telemetry_id"):
            local_telemetry = db.query(Telemetry.id).filter(
                Telemetry.rov_id == rec["telemetry_id"]
            ).first()
            telemetry_id = local_telemetry[0] if local_telemetry else None

        try:
            detection = Detection(
                id=generate_cuid(),
                rov_id=rov_id,
                session_id=session_id,
                telemetry_id=telemetry_id,
                species_name=rec.get("species_name", "unknown"),
                confidence=safe_float(rec.get("confidence"), "confidence", default=0.0),
                depth_at_detection=rec.get("depth_at_detection"),
                frame_number=rec.get("frame_number"),
                detected_at=detected_at,
                is_synced=True,
                created_at=now,
            )
        except ValueError as e:
            logger.warning(f"Skip record rov_id={rov_id}: {e}")
            skipped += 1
            continue

        db.add(detection)
        saved += 1

    db.commit()

    _last_sync_info["detections"]["last_synced_at"] = now.isoformat()
    _last_sync_info["detections"]["total_received"] += saved

    logger.info(f"Sync detections — saved={saved} skipped={skipped} session={session_id[:8]}...")

    return {
        "success": True,
        "message": f"{saved} detection records disimpan, {skipped} dilewati (duplikat/invalid)",
        "saved": saved,
        "skipped": skipped,
    }


# ==========================
# POST /api/sync/auv-status
# SPPI-47 syncAuvStatus
# ==========================
@router.post("/auv-status", status_code=status.HTTP_201_CREATED)
def sync_auv_status(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_sync_token),
):
    """
    Terima batch data navigasi AUV dari ROV dan simpan ke DB Base Station.

    Payload:
        session_id : str
        records    : list

    Setiap record:
        rov_id        : str   — ID asli dari DB ROV (untuk dedup)
        timestamp     : str   — ISO format
        roll          : float
        pitch         : float
        yaw           : float
        depth         : float
        heading       : str
        speed         : float
        gyroscope     : str   — opsional
        accelerometer : str   — opsional
        magnetometer  : str   — opsional
    """
    session_id = body.get("session_id") or body.get("sessionId")
    records: List[dict] = body.get("records", [])

    if not session_id or not records:
        raise HTTPException(
            status_code=400,
            detail="session_id dan records wajib diisi"
        )

    session = db.query(MonitoringSession).filter(
        MonitoringSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Sesi {session_id} tidak ditemukan di Base Station."
        )

    saved = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for rec in records:
        rov_id = rec.get("rov_id") or rec.get("id")

        existing = db.query(AUVStatus).filter(
            AUVStatus.rov_id == rov_id
        ).first() if rov_id else None

        if existing:
            skipped += 1
            continue

        try:
            ts = datetime.fromisoformat(rec.get("timestamp", now.isoformat()))
        except (ValueError, TypeError):
            ts = now

        try:
            auv_status = AUVStatus(
                id=generate_cuid(),
                rov_id=rov_id,
                session_id=session_id,
                timestamp=ts,
                roll=safe_float(rec.get("roll"), "roll", default=0.0),
                pitch=safe_float(rec.get("pitch"), "pitch", default=0.0),
                yaw=safe_float(rec.get("yaw"), "yaw", default=0.0),
                depth=safe_float(rec.get("depth"), "depth", default=0.0),
                heading=str(rec.get("heading", "N")),
                speed=safe_float(rec.get("speed"), "speed", default=0.0),
                gyroscope=rec.get("gyroscope"),
                accelerometer=rec.get("accelerometer"),
                magnetometer=rec.get("magnetometer"),
                is_synced=True,
                created_at=now,
            )
        except ValueError as e:
            logger.warning(f"Skip record rov_id={rov_id}: {e}")
            skipped += 1
            continue

        db.add(auv_status)
        saved += 1

    db.commit()

    _last_sync_info["auv_status"]["last_synced_at"] = now.isoformat()
    _last_sync_info["auv_status"]["total_received"] += saved

    logger.info(f"Sync auv_status — saved={saved} skipped={skipped} session={session_id[:8]}...")

    return {
        "success": True,
        "message": f"{saved} auv_status records disimpan, {skipped} dilewati (duplikat/invalid)",
        "saved": saved,
        "skipped": skipped,
    }


# ==========================
# GET /api/sync/status
# Cek info sync terakhir
# ==========================
@router.get("/status")
def get_sync_status(
    _: dict = Depends(get_current_user),
):
    """
    Tampilkan info sinkronisasi terakhir untuk monitoring.
    """
    return {
        "success": True,
        "data": _last_sync_info,
    }