"""
Sync sender — dijalankan di sisi ROV (Jetson Orin).

Job ini dipanggil oleh scheduler tiap X detik:
  1. Kirim sesi misi (baru / berubah status) ke Base Station
  2. Ambil data yang belum tersync (is_synced=False) dari SEMUA sesi,
     bukan hanya sesi Running — sisa data sesi yang sudah selesai ikut terkirim
  3. Kirim per sesi ke endpoint /api/sync/* di Base Station
  4. Jika berhasil, tandai is_synced=True di DB ROV

Kalau sesi belum sampai di Base Station (404), data sesi itu tetap
is_synced=False dan dicoba lagi di interval berikutnya.

Diimport dan didaftarkan di core/scheduler.py.
"""
import asyncio
import logging
import httpx
from typing import Callable, Dict, Optional, Tuple

logger = logging.getLogger("carter-backend")

# Di-set dari config.py
BASE_STATION_URL: Optional[str] = None
BASE_STATION_TOKEN: Optional[str] = None
SYNC_BATCH_SIZE = 50  # Maksimal record per sekali kirim

# Isi sesi terakhir yang sukses terkirim: {session_id: fingerprint}.
# Sengaja tidak memakai updated_at — kolom itu diisi campuran UTC (Python)
# dan jam lokal server (NOW() MySQL), jadi tidak bisa jadi watermark.
# In-memory: setelah restart semua sesi dikirim ulang sekali (upsert, aman).
_sent_sessions: Dict[str, Tuple] = {}


def init_sync_sender(base_station_url: str, token: str):
    """
    Inisialisasi URL dan token Base Station.
    Dipanggil dari setup_scheduler() di scheduler.py.
    """
    global BASE_STATION_URL, BASE_STATION_TOKEN
    BASE_STATION_URL = base_station_url.rstrip("/")
    BASE_STATION_TOKEN = token
    logger.info(f"Sync sender initialized — target: {BASE_STATION_URL}")


async def _post(path: str, payload: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await client.post(
            f"{BASE_STATION_URL}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {BASE_STATION_TOKEN}"},
        )


def _session_record(s) -> dict:
    return {
        "id": s.id,
        "location_name": s.location_name,
        "start_time": s.start_time.isoformat() if s.start_time else None,
        "end_time": s.end_time.isoformat() if s.end_time else None,
        "status": s.status.value,
        "owner_email": s.user.email if s.user else None,
    }


def _load_changed_sessions() -> list:
    """Sesi yang isinya berubah sejak terakhir terkirim (sinkron, jalan di thread)."""
    from database.connection import SessionLocal
    from database.models import MonitoringSession

    db = SessionLocal()
    try:
        changed = []
        for s in db.query(MonitoringSession).order_by(MonitoringSession.start_time.asc()).all():
            rec = _session_record(s)  # baca s.user di sini, sebelum sesi DB ditutup
            fingerprint = tuple(rec.values())
            if _sent_sessions.get(s.id) != fingerprint:
                changed.append((rec, fingerprint))
        return changed
    finally:
        db.close()


async def sync_sessions_job():
    """
    Kirim sesi misi yang baru / berubah (status, end_time, lokasi) ke Base Station.
    Data telemetri/deteksi/auv_status butuh sesinya ada dulu di Base Station.
    Query DB jalan di thread agar tidak memblokir event loop.
    """
    if not BASE_STATION_URL or not BASE_STATION_TOKEN:
        return

    try:
        changed = await asyncio.to_thread(_load_changed_sessions)

        for start in range(0, len(changed), SYNC_BATCH_SIZE):
            batch = changed[start:start + SYNC_BATCH_SIZE]
            response = await _post("/api/sync/sessions", {"records": [r for r, _ in batch]})
            if response.status_code not in (200, 201):
                logger.warning(f"Sync sessions gagal — status {response.status_code}")
                return

            skipped_ids = set(response.json().get("skipped_ids", []))
            for rec, fingerprint in batch:
                if rec["id"] not in skipped_ids:
                    _sent_sessions[rec["id"]] = fingerprint
            logger.info(f"Sync sessions — {len(batch) - len(skipped_ids)} sesi dikirim ke Base Station")

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("Sync sessions — Base Station tidak dapat dijangkau, akan retry")
    except Exception as e:
        logger.error(f"Sync sessions error: {e}")


def _load_pending_batches(model, order_col, to_record, ready_filter) -> list:
    """
    Satu batch baris is_synced=False per sesi (sinkron, jalan di thread).
    Return list (session_id, ids, records).
    """
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        pending = [model.is_synced == False]
        if ready_filter is not None:
            pending.append(ready_filter)

        session_ids = [
            sid for (sid,) in
            db.query(model.session_id).filter(*pending).distinct().all()
        ]

        batches = []
        for session_id in session_ids:
            unsynced = (
                db.query(model)
                .filter(model.session_id == session_id, *pending)
                .order_by(order_col.asc())
                .limit(SYNC_BATCH_SIZE)
                .all()
            )
            if unsynced:
                batches.append((
                    session_id,
                    [r.id for r in unsynced],
                    [to_record(r) for r in unsynced],
                ))
        return batches
    finally:
        db.close()


def _mark_synced(model, ids: list) -> None:
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        db.query(model).filter(model.id.in_(ids)).update(
            {"is_synced": True}, synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _sync_rows(
    model, order_col, path: str, label: str, to_record: Callable[[object], dict],
    ready_filter=None,
):
    """
    Kirim baris is_synced=False dari semua sesi, satu batch per sesi per tick.
    Satu sesi yang gagal (mis. belum ada di Base Station) tidak menahan sesi lain.
    ready_filter: syarat tambahan agar baris boleh dikirim sekarang.
    Query DB jalan di thread; hanya HTTP yang di event loop.
    """
    if not BASE_STATION_URL or not BASE_STATION_TOKEN:
        return

    try:
        batches = await asyncio.to_thread(
            _load_pending_batches, model, order_col, to_record, ready_filter
        )

        for session_id, ids, records in batches:
            response = await _post(path, {"session_id": session_id, "records": records})

            if response.status_code in (200, 201):
                await asyncio.to_thread(_mark_synced, model, ids)
                logger.info(f"Sync {label} — {len(ids)} records dikirim ke Base Station")
            elif response.status_code == 404:
                logger.info(f"Sync {label} — sesi {session_id[:8]}... belum ada di Base Station, retry nanti")
            else:
                logger.warning(f"Sync {label} gagal — status {response.status_code}")

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning(f"Sync {label} — Base Station tidak dapat dijangkau, akan retry")
    except Exception as e:
        logger.error(f"Sync {label} error: {e}")


async def sync_telemetry_job():
    """
    SPPI-45 syncTelemetry — kirim telemetri yang belum tersync ke Base Station.
    """
    from database.models import Telemetry

    await _sync_rows(
        Telemetry, Telemetry.timestamp, "/api/sync/telemetry", "telemetry",
        lambda t: {
            "rov_id": t.id,
            "timestamp": t.timestamp.isoformat(),
            "depth": t.depth,
            "ph_level": t.ph_level,
            "tds_value": t.tds_value,
            "dissolved_oxygen": t.dissolved_oxygen,
            "water_temp": t.water_temp,
        },
    )


async def sync_detections_job():
    """
    SPPI-46 syncDetections — kirim deteksi yang belum tersync ke Base Station.
    """
    from sqlalchemy import or_, select
    from database.models import Detection, Telemetry

    # Tahan deteksi sampai telemetri yang dirujuk sudah sampai di Base Station,
    # supaya Base Station bisa memetakan telemetry_id (bukan dikosongkan).
    telemetry_ready = or_(
        Detection.telemetry_id.is_(None),
        Detection.telemetry_id.in_(select(Telemetry.id).where(Telemetry.is_synced == True)),
    )

    await _sync_rows(
        Detection, Detection.detected_at, "/api/sync/detections", "detections",
        lambda d: {
            "rov_id": d.id,
            "telemetry_id": d.telemetry_id,
            "species_name": d.species_name,
            "confidence": d.confidence,
            "depth_at_detection": d.depth_at_detection,
            "frame_number": d.frame_number,
            "detected_at": d.detected_at.isoformat(),
        },
        ready_filter=telemetry_ready,
    )


async def sync_auv_status_job():
    """
    SPPI-47 syncAuvStatus — kirim data navigasi yang belum tersync ke Base Station.
    """
    from database.models import AUVStatus

    await _sync_rows(
        AUVStatus, AUVStatus.timestamp, "/api/sync/auv-status", "auv_status",
        lambda s: {
            "rov_id": s.id,
            "timestamp": s.timestamp.isoformat(),
            "roll": s.roll,
            "pitch": s.pitch,
            "yaw": s.yaw,
            "depth": s.depth,
            "heading": s.heading,
            "speed": s.speed,
            "gyroscope": s.gyroscope,
            "accelerometer": s.accelerometer,
            "magnetometer": s.magnetometer,
        },
    )
