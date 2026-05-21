import asyncio
import logging
import os
import signal
import sys
import threading
import torch
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

# Fix Ctrl+C di Windows — event loop default Windows tidak handle SIGINT dengan benar
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import SAVE_DETECTIONS_ENABLED, SAVE_INTERVAL_SECONDS
from models.yolo_detector import load_custom_model, get_device_info
from database.connection import check_db_connection, init_db
from video.recording import initialize_recordings_dir, cleanup_all_recordings
from webrtc.peer_connection import cleanup_all
from api.routes import setup_routes
from core.scheduler import scheduler, setup_scheduler

# Routers fase 2
from routers.auth import router as auth_router

# Routers fase 4
from routers.users import router as users_router
from routers.telemetry import router as telemetry_router
from routers.auv_status import router as auv_status_router
from routers.detections import router as detections_router
from routers.recordings import router as recordings_router
from routers.analytics import router as analytics_router
from routers.sessions import router as sessions_router
from routers.fish_counts import router as fish_counts_router

# Routers fase 5 — Sync ROV → Base Station (SPPI 45-47)
from routers.sync import router as sync_router

# ==========================
# Logging Setup
# ==========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("carter-backend")

# ==========================
# Global Resources
# ==========================
inference_executor = ThreadPoolExecutor(max_workers=2)


def _install_force_exit_handler(timeout: int = 8):
    """Pasang fallback: jika proses belum mati dalam `timeout` detik setelah
    Ctrl+C, paksa keluar dengan os._exit(0) agar tidak macet selamanya."""
    original = signal.getsignal(signal.SIGINT)

    def _handler(signum, frame):
        def _force():
            import time
            time.sleep(timeout)
            logger.warning(f"Force exit setelah {timeout}s (proses tidak berhenti sendiri)")
            os._exit(0)
        t = threading.Thread(target=_force, daemon=True, name="force-exit-watchdog")
        t.start()
        if callable(original):
            original(signum, frame)
        else:
            raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handler)


_install_force_exit_handler(timeout=8)


# ==========================
# Lifespan Manager
# ==========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Starting Carter Island Backend...")
    logger.info("=" * 60)

    # Cek dan inisialisasi database
    if not check_db_connection():
        logger.error("Tidak bisa konek ke database! Periksa DATABASE_URL di .env")
        raise RuntimeError("Database connection failed")
    init_db()

    # Abort sesi RUNNING yang tertinggal dari restart sebelumnya
    try:
        from database.connection import SessionLocal
        from database.models import MonitoringSession, SessionStatus
        from datetime import datetime, timezone
        _db = SessionLocal()
        try:
            stale = _db.query(MonitoringSession).filter(
                MonitoringSession.status == SessionStatus.RUNNING
            ).all()
            if stale:
                now = datetime.now(timezone.utc)
                for s in stale:
                    s.status = SessionStatus.ABORTED
                    s.end_time = now
                    s.updated_at = now
                _db.commit()
                logger.warning(f"Auto-aborted {len(stale)} sesi RUNNING dari restart sebelumnya")
        finally:
            _db.close()
    except Exception as _e:
        logger.warning(f"Gagal auto-abort sesi lama: {_e}")

    # Load YOLO model
    load_custom_model()
    logger.info(f"Device: {get_device_info()}")

    # Konfigurasi deteksi
    if SAVE_DETECTIONS_ENABLED:
        logger.info("Database saving enabled — detections saved directly via SQLAlchemy")
        logger.info(f"Save interval: {SAVE_INTERVAL_SECONDS}s")
    else:
        logger.info("Database saving disabled")

    # Jalankan background scheduler
    setup_scheduler()
    scheduler.start()
    logger.info("Background scheduler started")

    logger.info("=" * 60)
    logger.info("Backend ready!")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

        cleanup_all_recordings()

        try:
            await asyncio.wait_for(cleanup_all(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Cleanup timeout — forcing shutdown")

        inference_executor.shutdown(wait=False)

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("Shutdown complete")
    except Exception as e:
        logger.warning(f"Shutdown error: {e}")


# ==========================
# FastAPI App
# ==========================
app = FastAPI(
    title="Carter Island Unified Backend",
    description="ROV monitoring — fish detection, telemetry, streaming",
    version="5.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes lama (WebRTC, recording start/stop, model info)
setup_routes(app)

# Routes baru
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(telemetry_router)
app.include_router(auv_status_router)
app.include_router(detections_router)
app.include_router(recordings_router)
app.include_router(analytics_router)
app.include_router(sessions_router)
app.include_router(fish_counts_router)

# Sync ROV → Base Station (SPPI 45-47)
app.include_router(sync_router)


# ==========================
# Main Entry Point
# ==========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False,
        loop="asyncio",
        timeout_graceful_shutdown=5,
    )