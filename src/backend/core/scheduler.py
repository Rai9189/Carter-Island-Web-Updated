"""
Background scheduler menggunakan APScheduler.

Job yang berjalan:
  - health_check_job    : tiap 5 detik — cek koneksi ROV, simpan status navigasi
                          & kualitas air (pH/TDS/DO/suhu) dari Raspberry Pi
  - sync_sessions_job   : tiap X detik — kirim sesi misi baru/berubah ke Base Station
  - sync_telemetry_job  : tiap X detik — SPPI-45 kirim telemetri ke Base Station
  - sync_detections_job : tiap X detik — SPPI-46 kirim deteksi ke Base Station
  - sync_auv_status_job : tiap X detik — SPPI-47 kirim auv_status ke Base Station

Catatan retensi:
  - Data misi TIDAK dihapus otomatis (keputusan 2026-09-24). Hapus misi
    dilakukan manual oleh admin lewat DELETE /api/sessions/{id}.

Catatan sync:
  - Job sync hanya aktif jika BASE_STATION_URL diisi di .env
  - Jika Base Station tidak dapat dijangkau, data tetap aman di ROV (is_synced=False)
  - Saat koneksi pulih, scheduler otomatis retry di interval berikutnya
"""
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import BASE_STATION_URL, BASE_STATION_SYNC_TOKEN, SYNC_INTERVAL_SECONDS
from core.validation import safe_float

logger = logging.getLogger("carter-backend")

# URL Raspberry Pi dan MediaMTX
RASPI_TELEMETRY_URL = "http://192.168.2.2:14552/telemetry"
MEDIAMTX_URL        = "http://192.168.2.2:8889/cam/"

# Singleton scheduler
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

# State koneksi ROV
_is_rov_online: bool = False


# Nama key sensor kualitas air di JSON Raspberry Pi belum pasti (2026-09-25),
# jadi beberapa alias diterima — dicari di level atas JSON atau di objek
# "water_quality". Sesuaikan setelah format JSON asli diketahui.
WATER_QUALITY_KEYS = {
    "ph_level":         ("ph", "ph_level", "phLevel"),
    "tds_value":        ("tds", "tds_value", "tdsValue"),
    "dissolved_oxygen": ("do", "dissolved_oxygen", "dissolvedOxygen"),
    "water_temp":       ("water_temp", "waterTemp", "temperature", "temp"),
}


def _read_water_quality(data: dict) -> Optional[dict]:
    """
    Ambil pH/TDS/DO/suhu air dari JSON Raspberry Pi.
    Return None kalau ada yang hilang / bukan angka — baris telemetri hanya
    disimpan kalau keempatnya lengkap, supaya sensor mati tidak tercatat 0
    dan merusak rata-rata (keputusan 2026-09-25).
    """
    sources = [data]
    if isinstance(data.get("water_quality"), dict):
        sources.insert(0, data["water_quality"])

    values = {}
    for field, aliases in WATER_QUALITY_KEYS.items():
        raw = next((src[k] for src in sources for k in aliases if src.get(k) is not None), None)
        try:
            values[field] = safe_float(raw, field)
        except ValueError:
            return None
    return values


# ==========================
# Job 1 — Health check tiap 5 detik
# ==========================
async def health_check_job():
    """
    Cek koneksi ROV via Raspberry Pi telemetri endpoint.
    Jika data navigasi tersedia (attitude/compass), simpan ke auv_status.
    Jika pH/TDS/DO/suhu air lengkap, simpan ke telemetries.
    """
    global _is_rov_online

    from database.connection import SessionLocal
    from database.models import AUVStatus, Telemetry
    from core.cuid import generate_cuid

    telemetry_data = None
    is_online = False

    # ── Cek 1: Telemetri navigasi dari Raspberry Pi ──
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(RASPI_TELEMETRY_URL)

            if response.is_success:
                data = response.json()
                if isinstance(data, dict):
                    telemetry_data = data
                    is_online = all(k in data for k in ("attitude", "compass"))

    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    except Exception as e:
        logger.warning(f"Health check — Raspi error: {e}")

    # ── Cek 2: MediaMTX fallback ──
    if not is_online:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.head(MEDIAMTX_URL)
                if response.is_success:
                    is_online = True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        except Exception as e:
            logger.warning(f"Health check — MediaMTX error: {e}")

    _is_rov_online = is_online

    if telemetry_data is None:
        return

    has_navigation = all(k in telemetry_data for k in ("attitude", "compass"))
    water_quality = _read_water_quality(telemetry_data)
    if not has_navigation and water_quality is None:
        return

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        attitude = telemetry_data.get("attitude", {})
        compass  = telemetry_data.get("compass", {})

        from database.models import MonitoringSession, SessionStatus
        active_session = (
            db.query(MonitoringSession)
            .filter(MonitoringSession.status == SessionStatus.RUNNING)
            .order_by(MonitoringSession.start_time.desc())
            .first()
        )

        if active_session is None:
            logger.debug("Health check — tidak ada sesi aktif, skip simpan AUVStatus/Telemetry")
            return

        if has_navigation:
            auv_status = AUVStatus(
                id=generate_cuid(),
                session_id=active_session.id,
                timestamp=now,
                roll=float(attitude.get("roll_deg", 0.0)),
                pitch=float(attitude.get("pitch_deg", 0.0)),
                yaw=float(attitude.get("yaw_deg", 0.0)),
                depth=float(telemetry_data.get("depth", 0.0)),
                heading=str(compass.get("heading_deg", "0")),
                speed=float(telemetry_data.get("speed", 0.0)),
                gyroscope=None,
                accelerometer=None,
                magnetometer=None,
                rov_id=None,
                is_synced=False,
                created_at=now,
            )
            db.add(auv_status)

        if water_quality is not None:
            try:
                depth = safe_float(telemetry_data.get("depth"), "depth", default=0.0)
            except ValueError:
                depth = 0.0
            db.add(Telemetry(
                id=generate_cuid(),
                session_id=active_session.id,
                timestamp=now,
                depth=depth,
                is_synced=False,
                created_at=now,
                **water_quality,
            ))

        db.commit()
        logger.debug(f"Health check data saved — session {active_session.id[:8]}...")

    except Exception as e:
        db.rollback()
        logger.error(f"Health check — status save error: {e}")
    finally:
        db.close()


# ==========================
# Helper — cek status ROV
# ==========================
def is_rov_online() -> bool:
    return _is_rov_online


# ==========================
# Setup scheduler
# ==========================
def setup_scheduler():
    """
    Daftarkan semua job ke scheduler.
    Dipanggil sekali saat startup dari main.py lifespan.
    """
    # Job 1 — Health check
    scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(seconds=5),
        id="health_check",
        name="AUV & MediaMTX Health Check",
        replace_existing=True,
        misfire_grace_time=10,
    )

    logger.info("Scheduler jobs registered:")
    logger.info("  - health_check_job : tiap 5 detik")

    # Job 3/4/5 — Sync ROV → Base Station (hanya aktif jika dikonfigurasi)
    if BASE_STATION_URL and BASE_STATION_SYNC_TOKEN:
        from core.sync_sender import (
            init_sync_sender,
            sync_sessions_job,
            sync_telemetry_job,
            sync_detections_job,
            sync_auv_status_job,
        )

        init_sync_sender(BASE_STATION_URL, BASE_STATION_SYNC_TOKEN)

        scheduler.add_job(
            sync_sessions_job,
            trigger=IntervalTrigger(seconds=SYNC_INTERVAL_SECONDS),
            id="sync_sessions",
            name="Sync Sessions → Base Station",
            replace_existing=True,
            misfire_grace_time=15,
        )

        scheduler.add_job(
            sync_telemetry_job,
            trigger=IntervalTrigger(seconds=SYNC_INTERVAL_SECONDS),
            id="sync_telemetry",
            name="SPPI-45 Sync Telemetry → Base Station",
            replace_existing=True,
            misfire_grace_time=15,
        )

        scheduler.add_job(
            sync_detections_job,
            trigger=IntervalTrigger(seconds=SYNC_INTERVAL_SECONDS),
            id="sync_detections",
            name="SPPI-46 Sync Detections → Base Station",
            replace_existing=True,
            misfire_grace_time=15,
        )

        scheduler.add_job(
            sync_auv_status_job,
            trigger=IntervalTrigger(seconds=SYNC_INTERVAL_SECONDS),
            id="sync_auv_status",
            name="SPPI-47 Sync AUV Status → Base Station",
            replace_existing=True,
            misfire_grace_time=15,
        )

        logger.info(f"  - sync_sessions_job   : tiap {SYNC_INTERVAL_SECONDS} detik")
        logger.info(f"  - sync_telemetry_job  : tiap {SYNC_INTERVAL_SECONDS} detik (SPPI-45)")
        logger.info(f"  - sync_detections_job : tiap {SYNC_INTERVAL_SECONDS} detik (SPPI-46)")
        logger.info(f"  - sync_auv_status_job : tiap {SYNC_INTERVAL_SECONDS} detik (SPPI-47)")
    else:
        logger.info("  - Sync jobs DINONAKTIFKAN (BASE_STATION_URL tidak diisi di .env)")