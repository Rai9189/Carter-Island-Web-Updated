"""
Sync sender — dijalankan di sisi ROV (Jetson Orin).

Job ini dipanggil oleh scheduler tiap X detik:
  1. Cek koneksi ke Base Station
  2. Ambil data yang belum tersync (is_synced=False)
  3. Kirim ke endpoint /api/sync/* di Base Station
  4. Jika berhasil, tandai is_synced=True di DB ROV

Diimport dan didaftarkan di core/scheduler.py.
"""
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("carter-backend")

# Di-set dari config.py
BASE_STATION_URL: Optional[str] = None
BASE_STATION_TOKEN: Optional[str] = None
SYNC_BATCH_SIZE = 50  # Maksimal record per sekali kirim


def init_sync_sender(base_station_url: str, token: str):
    """
    Inisialisasi URL dan token Base Station.
    Dipanggil dari setup_scheduler() di scheduler.py.
    """
    global BASE_STATION_URL, BASE_STATION_TOKEN
    BASE_STATION_URL = base_station_url.rstrip("/")
    BASE_STATION_TOKEN = token
    logger.info(f"Sync sender initialized — target: {BASE_STATION_URL}")


async def sync_telemetry_job():
    """
    SPPI-45 syncTelemetry — kirim telemetri yang belum tersync ke Base Station.
    """
    if not BASE_STATION_URL or not BASE_STATION_TOKEN:
        return

    from database.connection import SessionLocal
    from database.models import Telemetry, MonitoringSession

    db = SessionLocal()
    try:
        # Ambil sesi aktif
        active_session = (
            db.query(MonitoringSession)
            .filter(MonitoringSession.status == "Running")
            .order_by(MonitoringSession.start_time.desc())
            .first()
        )
        if not active_session:
            return

        # Ambil data yang belum tersync
        unsynced = (
            db.query(Telemetry)
            .filter(
                Telemetry.session_id == active_session.id,
                Telemetry.is_synced == False,
            )
            .order_by(Telemetry.timestamp.asc())
            .limit(SYNC_BATCH_SIZE)
            .all()
        )

        if not unsynced:
            return

        # Siapkan payload
        records = [
            {
                "rov_id": t.id,
                "timestamp": t.timestamp.isoformat(),
                "depth": t.depth,
                "ph_level": t.ph_level,
                "tds_value": t.tds_value,
                "dissolved_oxygen": t.dissolved_oxygen,
                "water_temp": t.water_temp,
            }
            for t in unsynced
        ]

        # Kirim ke Base Station
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BASE_STATION_URL}/api/sync/telemetry",
                json={"session_id": active_session.id, "records": records},
                headers={"Authorization": f"Bearer {BASE_STATION_TOKEN}"},
            )

        if response.status_code in (200, 201):
            # Tandai sudah tersync
            ids = [t.id for t in unsynced]
            db.query(Telemetry).filter(Telemetry.id.in_(ids)).update(
                {"is_synced": True}, synchronize_session=False
            )
            db.commit()
            logger.info(f"Sync telemetry — {len(unsynced)} records dikirim ke Base Station")
        else:
            logger.warning(f"Sync telemetry gagal — status {response.status_code}")

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("Sync telemetry — Base Station tidak dapat dijangkau, akan retry")
    except Exception as e:
        db.rollback()
        logger.error(f"Sync telemetry error: {e}")
    finally:
        db.close()


async def sync_detections_job():
    """
    SPPI-46 syncDetections — kirim deteksi yang belum tersync ke Base Station.
    """
    if not BASE_STATION_URL or not BASE_STATION_TOKEN:
        return

    from database.connection import SessionLocal
    from database.models import Detection, MonitoringSession

    db = SessionLocal()
    try:
        active_session = (
            db.query(MonitoringSession)
            .filter(MonitoringSession.status == "Running")
            .order_by(MonitoringSession.start_time.desc())
            .first()
        )
        if not active_session:
            return

        unsynced = (
            db.query(Detection)
            .filter(
                Detection.session_id == active_session.id,
                Detection.is_synced == False,
            )
            .order_by(Detection.detected_at.asc())
            .limit(SYNC_BATCH_SIZE)
            .all()
        )

        if not unsynced:
            return

        records = [
            {
                "rov_id": d.id,
                "telemetry_id": d.telemetry_id,
                "species_name": d.species_name,
                "confidence": d.confidence,
                "depth_at_detection": d.depth_at_detection,
                "frame_number": d.frame_number,
                "detected_at": d.detected_at.isoformat(),
            }
            for d in unsynced
        ]

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BASE_STATION_URL}/api/sync/detections",
                json={"session_id": active_session.id, "records": records},
                headers={"Authorization": f"Bearer {BASE_STATION_TOKEN}"},
            )

        if response.status_code in (200, 201):
            ids = [d.id for d in unsynced]
            db.query(Detection).filter(Detection.id.in_(ids)).update(
                {"is_synced": True}, synchronize_session=False
            )
            db.commit()
            logger.info(f"Sync detections — {len(unsynced)} records dikirim ke Base Station")
        else:
            logger.warning(f"Sync detections gagal — status {response.status_code}")

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("Sync detections — Base Station tidak dapat dijangkau, akan retry")
    except Exception as e:
        db.rollback()
        logger.error(f"Sync detections error: {e}")
    finally:
        db.close()


async def sync_auv_status_job():
    """
    SPPI-47 syncAuvStatus — kirim data navigasi yang belum tersync ke Base Station.
    """
    if not BASE_STATION_URL or not BASE_STATION_TOKEN:
        return

    from database.connection import SessionLocal
    from database.models import AUVStatus, MonitoringSession

    db = SessionLocal()
    try:
        active_session = (
            db.query(MonitoringSession)
            .filter(MonitoringSession.status == "Running")
            .order_by(MonitoringSession.start_time.desc())
            .first()
        )
        if not active_session:
            return

        unsynced = (
            db.query(AUVStatus)
            .filter(
                AUVStatus.session_id == active_session.id,
                AUVStatus.is_synced == False,
            )
            .order_by(AUVStatus.timestamp.asc())
            .limit(SYNC_BATCH_SIZE)
            .all()
        )

        if not unsynced:
            return

        records = [
            {
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
            }
            for s in unsynced
        ]

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BASE_STATION_URL}/api/sync/auv-status",
                json={"session_id": active_session.id, "records": records},
                headers={"Authorization": f"Bearer {BASE_STATION_TOKEN}"},
            )

        if response.status_code in (200, 201):
            ids = [s.id for s in unsynced]
            db.query(AUVStatus).filter(AUVStatus.id.in_(ids)).update(
                {"is_synced": True}, synchronize_session=False
            )
            db.commit()
            logger.info(f"Sync auv_status — {len(unsynced)} records dikirim ke Base Station")
        else:
            logger.warning(f"Sync auv_status gagal — status {response.status_code}")

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("Sync auv_status — Base Station tidak dapat dijangkau, akan retry")
    except Exception as e:
        db.rollback()
        logger.error(f"Sync auv_status error: {e}")
    finally:
        db.close()