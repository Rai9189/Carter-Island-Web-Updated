"""
Background scheduler menggunakan APScheduler.

Menggantikan dua endpoint polling dari frontend:
  - /api/health/check      → job tiap 5 detik
  - /api/mediamtx/health   → digabung ke job yang sama
  - /api/maintenance/cleanup → job tiap hari jam 00:00

Dengan scheduler ini, frontend TIDAK perlu lagi polling
health check ke server. Server yang aktif mengecek sendiri
dan menyimpan hasilnya ke database.
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
MEDIAMTX_URL = "http://192.168.2.2:8889/cam/"

# Singleton scheduler
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

# State untuk tracking uptime
_first_connected_time: datetime | None = None


# ==========================
# Job 1 — Health check tiap 5 detik
# ==========================
async def health_check_job():
    """
    Cek status AUV dan MediaMTX, simpan ke database.

    Menggabungkan logika dari:
    - /api/health/check       → cek telemetri Raspi, deteksi perubahan data
    - /api/mediamtx/health    → cek aksesibilitas MediaMTX player

    Hasil disimpan ke tabel auv_status.
    """
    global _first_connected_time

    from database.connection import SessionLocal
    from database.models import Telemetry, AUVStatus
    from core.cuid import generate_cuid

    is_online = False
    connection_strength = "Disconnected"
    telemetry_data = None

    # ── Cek 1: Telemetri dari Raspberry Pi ──
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(RASPI_TELEMETRY_URL)

            if response.ok:
                data = response.json()

                if all(k in data for k in ("attitude", "compass", "battery", "health")):
                    telemetry_data = data

                    # Simpan telemetri ke database
                    db = SessionLocal()
                    try:
                        now = datetime.now(timezone.utc)

                        # Cek apakah data berubah dari sebelumnya
                        prev = db.query(Telemetry).order_by(
                            Telemetry.timestamp.desc()
                        ).first()

                        data_changing = _is_telemetry_changing(data, prev)

                        # Simpan telemetri baru
                        telemetry = Telemetry(
                            id=generate_cuid(),
                            roll_deg=float(data["attitude"]["roll_deg"]),
                            pitch_deg=float(data["attitude"]["pitch_deg"]),
                            yaw_deg=float(data["attitude"]["yaw_deg"]),
                            heading_deg=float(data["compass"]["heading_deg"]),
                            voltage_v=float(data["battery"]["voltage_v"]),
                            current_a=data["battery"].get("current_a"),
                            remaining_percent=float(data["battery"]["remaining_percent"]),
                            consumed_mah=data["battery"].get("consumed_mAh"),
                            gyro_cal=bool(data["health"]["gyro_cal"]),
                            accel_cal=bool(data["health"]["accel_cal"]),
                            mag_cal=bool(data["health"]["mag_cal"]),
                            timestamp=now,
                            created_at=now,
                        )
                        db.add(telemetry)
                        db.commit()

                        # AUV online jika data berubah
                        is_online = data_changing
                        connection_strength = "Strong" if is_online else "Disconnected"

                    except Exception as e:
                        db.rollback()
                        logger.error(f"Health check — DB error: {e}")
                    finally:
                        db.close()

    except (httpx.ConnectError, httpx.TimeoutException):
        # Raspi tidak bisa dihubungi — coba cek MediaMTX sebagai fallback
        pass
    except Exception as e:
        logger.warning(f"Health check — Raspi error: {e}")

    # ── Cek 2: MediaMTX (fallback jika Raspi tidak terdeteksi) ──
    if not is_online:
        try:
            start = datetime.now(timezone.utc)
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.head(MEDIAMTX_URL)
                response_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

                if response.is_success:
                    is_online = True
                    if response_ms < 500:
                        connection_strength = "Strong"
                    elif response_ms < 1500:
                        connection_strength = "Moderate"
                    else:
                        connection_strength = "Weak"

        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        except Exception as e:
            logger.warning(f"Health check — MediaMTX error: {e}")

    # ── Simpan AUV status ke database ──
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Kelola first connected time untuk perhitungan uptime
        global _first_connected_time
        if is_online:
            if _first_connected_time is None:
                _first_connected_time = now
        else:
            _first_connected_time = None

        uptime_seconds = 0
        if is_online and _first_connected_time:
            uptime_seconds = int((now - _first_connected_time).total_seconds())

        status = AUVStatus(
            id=generate_cuid(),
            is_online=is_online,
            connection_strength=connection_strength,
            uptime_seconds=uptime_seconds,
            location_status="Active",
            last_stream_time=_first_connected_time,
            timestamp=now,
            created_at=now,
        )
        db.add(status)
        db.commit()

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
    Hapus data telemetri dan AUV status yang lebih dari 7 hari.

    Menggantikan endpoint /api/maintenance/cleanup yang
    sebelumnya harus dipanggil manual dari frontend.
    """
    from database.connection import SessionLocal
    from database.models import Telemetry, AUVStatus

    db = SessionLocal()
    try:
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        deleted_telemetry = db.query(Telemetry).filter(
            Telemetry.timestamp < seven_days_ago
        ).delete()

        deleted_auv = db.query(AUVStatus).filter(
            AUVStatus.timestamp < seven_days_ago
        ).delete()

        db.commit()

        logger.info(
            f"Cleanup selesai — "
            f"telemetry: {deleted_telemetry} rows, "
            f"auv_status: {deleted_auv} rows dihapus"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup job error: {e}")
    finally:
        db.close()


# ==========================
# Helper — cek perubahan telemetri
# ==========================
def _is_telemetry_changing(current: dict, previous) -> bool:
    """
    Cek apakah data telemetri berubah dari pembacaan sebelumnya.
    AUV dianggap online hanya jika datanya aktif berubah.
    """
    if previous is None:
        return True  # Pertama kali, anggap berubah

    attitude_changed = (
        current["attitude"]["roll_deg"] != previous.roll_deg or
        current["attitude"]["pitch_deg"] != previous.pitch_deg or
        current["attitude"]["yaw_deg"] != previous.yaw_deg
    )
    compass_changed = current["compass"]["heading_deg"] != previous.heading_deg
    battery_changed = (
        current["battery"]["voltage_v"] != previous.voltage_v or
        current["battery"]["remaining_percent"] != previous.remaining_percent
    )
    health_changed = (
        current["health"]["gyro_cal"] != previous.gyro_cal or
        current["health"]["accel_cal"] != previous.accel_cal or
        current["health"]["mag_cal"] != previous.mag_cal
    )

    return attitude_changed or compass_changed or battery_changed or health_changed


# ==========================
# Setup scheduler
# ==========================
def setup_scheduler():
    """
    Daftarkan semua job ke scheduler.
    Dipanggil sekali saat startup dari main.py lifespan.
    """
    # Job health check — tiap 5 detik
    scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(seconds=5),
        id="health_check",
        name="AUV & MediaMTX Health Check",
        replace_existing=True,
        misfire_grace_time=10,  # Toleransi keterlambatan 10 detik
    )

    # Job cleanup — tiap hari jam 00:00 WIB
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