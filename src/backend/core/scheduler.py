"""
Background scheduler menggunakan APScheduler.

Job yang berjalan:
  - health_check_job : tiap 5 detik — cek koneksi ROV & simpan status navigasi
  - cleanup_job      : tiap hari jam 00:00 WIB — hapus data lama

Perubahan dari versi lama:
  - AUVStatus tidak lagi menyimpan is_online/connection_strength/uptime_seconds
  - AUVStatus sekarang menyimpan data navigasi: roll/pitch/yaw/depth/heading/speed
  - Telemetry tidak lagi disimpan di scheduler (data kualitas air dari sensor ROV,
    bukan dari Raspberry Pi — akan diisi oleh endpoint sync SPPI-45)
  - Health check tetap cek koneksi ke Raspberry Pi & MediaMTX,
    tapi hanya simpan AUVStatus navigasi jika data tersedia
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("carter-backend")

# URL Raspberry Pi dan MediaMTX
RASPI_TELEMETRY_URL = "http://192.168.2.2:14552/telemetry"
MEDIAMTX_URL        = "http://192.168.2.2:8889/cam/"

# Singleton scheduler
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

# State koneksi ROV
_is_rov_online: bool = False


# ==========================
# Job 1 — Health check tiap 5 detik
# ==========================
async def health_check_job():
    """
    Cek koneksi ROV via Raspberry Pi telemetri endpoint.
    Jika data navigasi tersedia (attitude/compass), simpan ke auv_status.
    Jika tidak tersedia, cek MediaMTX sebagai fallback (tidak simpan ke DB).
    """
    global _is_rov_online

    from database.connection import SessionLocal
    from database.models import AUVStatus
    from core.cuid import generate_cuid

    telemetry_data = None
    is_online = False

    # ── Cek 1: Telemetri navigasi dari Raspberry Pi ──
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(RASPI_TELEMETRY_URL)

            if response.is_success:
                data = response.json()

                # Pastikan payload navigasi tersedia
                if all(k in data for k in ("attitude", "compass")):
                    telemetry_data = data
                    is_online = True

    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    except Exception as e:
        logger.warning(f"Health check — Raspi error: {e}")

    # ── Cek 2: MediaMTX fallback (hanya cek koneksi, tidak simpan) ──
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

    # ── Simpan AUVStatus navigasi jika data Raspi tersedia ──
    if telemetry_data is None:
        return  # Tidak ada data navigasi, tidak perlu simpan

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        attitude = telemetry_data.get("attitude", {})
        compass  = telemetry_data.get("compass", {})

        # session_id diisi None karena health check berjalan
        # di luar sesi misi — data navigasi background ini
        # tidak terikat ke monitoring_sessions tertentu.
        # Untuk data dalam sesi, gunakan endpoint sync SPPI-45.
        #
        # CATATAN: karena session_id nullable=False di model,
        # health check hanya menyimpan jika ada sesi aktif.
        # Jika tidak ada sesi aktif, skip saja.
        from database.models import MonitoringSession
        active_session = (
            db.query(MonitoringSession)
            .filter(MonitoringSession.status == "Running")
            .order_by(MonitoringSession.start_time.desc())
            .first()
        )

        if active_session is None:
            logger.debug("Health check — tidak ada sesi aktif, skip simpan AUVStatus")
            return

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
            created_at=now,
        )
        db.add(auv_status)
        db.commit()
        logger.debug(f"AUVStatus saved — session {active_session.id[:8]}...")

    except Exception as e:
        db.rollback()
        logger.error(f"Health check — status save error: {e}")
    finally:
        db.close()


# ==========================
# Job 2 — Cleanup data lama tiap hari jam 00:00
# ==========================
async def cleanup_job():
    """
    Hapus data telemetri, auv_status, dan deteksi yang lebih dari 30 hari.
    Sesi yang sudah Completed/Aborted lebih dari 30 hari juga dihapus
    beserta semua data anaknya (cascade).
    """
    from database.connection import SessionLocal
    from database.models import Telemetry, AUVStatus, MonitoringSession

    db = SessionLocal()
    try:
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # Hapus sesi lama yang sudah selesai — cascade ke semua tabel anak
        deleted_sessions = (
            db.query(MonitoringSession)
            .filter(
                MonitoringSession.status.in_(["Completed", "Aborted"]),
                MonitoringSession.created_at < thirty_days_ago,
            )
            .delete(synchronize_session=False)
        )

        db.commit()
        logger.info(
            f"Cleanup selesai — {deleted_sessions} sesi lama dihapus "
            f"(beserta semua data terkait)"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup job error: {e}")
    finally:
        db.close()


# ==========================
# Helper — cek status ROV
# ==========================
def is_rov_online() -> bool:
    """Cek apakah ROV sedang online berdasarkan hasil health check terakhir."""
    return _is_rov_online


# ==========================
# Setup scheduler
# ==========================
def setup_scheduler():
    """
    Daftarkan semua job ke scheduler.
    Dipanggil sekali saat startup dari main.py lifespan.
    """
    scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(seconds=5),
        id="health_check",
        name="AUV & MediaMTX Health Check",
        replace_existing=True,
        misfire_grace_time=10,
    )

    scheduler.add_job(
        cleanup_job,
        trigger=CronTrigger(hour=0, minute=0, timezone="Asia/Jakarta"),
        id="daily_cleanup",
        name="Daily Database Cleanup",
        replace_existing=True,
    )

    logger.info("Scheduler jobs registered:")
    logger.info("  - health_check_job: tiap 5 detik")
    logger.info("  - cleanup_job: tiap hari jam 00:00 WIB")