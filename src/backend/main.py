import logging
import torch
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

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

# ==========================
# Logging Setup
# ==========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("carter-backend")

# ==========================
# Global Resources
# ==========================
inference_executor = ThreadPoolExecutor(max_workers=2)


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
        await cleanup_all()
        inference_executor.shutdown(wait=True)

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
# FIX: allow_origins tidak boleh "*" kalau allow_credentials=True
# Harus spesifik menyebut origin frontend
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
        access_log=False
    )