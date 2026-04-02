import os
import uuid

# ==========================
# Streaming / Encoder Settings
# ==========================
RTSP_URL = os.getenv("RTSP_URL", "rtsp://192.168.2.2:8554/cam")
RTSP_TRANSPORT = os.getenv("RTSP_TRANSPORT", "udp")
TARGET_FPS = int(os.getenv("TARGET_FPS", "30"))
RESIZE_WIDTH = int(os.getenv("RESIZE_WIDTH", "1280"))
RESIZE_HEIGHT = int(os.getenv("RESIZE_HEIGHT", "720"))

# ==========================
# Bitrate Control
# ==========================
MAX_BITRATE_KBPS_DEFAULT = int(os.getenv("MAX_BITRATE_KBPS", "4500"))
MIN_BITRATE_KBPS_FLOOR = int(os.getenv("MIN_BITRATE_KBPS", "2500"))
BITRATE_REAPPLY_SEC = float(os.getenv("BITRATE_REAPPLY_SEC", "4.0"))
PREFER_CODEC = os.getenv("PREFER_CODEC", "h264").lower()
DISABLE_TWCC_REM = os.getenv("DISABLE_TWCC_REMB", "1") == "1"

# ==========================
# Database Saving Config
# ==========================
SAVE_DETECTIONS_ENABLED = os.getenv("SAVE_DETECTIONS_ENABLED", "true").lower() == "true"
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
SAVE_INTERVAL_SECONDS = float(os.getenv("SAVE_INTERVAL_SECONDS", "5.0"))
MIN_DETECTIONS_TO_SAVE = int(os.getenv("MIN_DETECTIONS_TO_SAVE", "1"))

# ==========================
# Recording Settings
# ==========================
import tempfile
RECORDINGS_DIR = tempfile.gettempdir()

# ==========================
# Model Settings
# ==========================
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "16sept.pt")
YOLO_CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.45"))
YOLO_IOU_THRESHOLD = float(os.getenv("YOLO_IOU_THRESHOLD", "0.5"))
YOLO_MAX_DETECTIONS = int(os.getenv("YOLO_MAX_DETECTIONS", "30"))

# ==========================
# Session ID
# ==========================
streaming_session_id = str(uuid.uuid4())

"""
Tambahan konfigurasi di config.py yang sudah ada.

Tambahkan baris-baris ini ke file config.py yang sudah ada
di src/backend/config.py — JANGAN timpa file aslinya,
cukup tambahkan bagian DATABASE_URL di bawah.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================
# TAMBAHAN BARU — Database
# ==========================

# Format dari .env: DATABASE_URL="mysql://user:pass@host:3306/dbname"
# Prisma pakai format mysql://, SQLAlchemy butuh mysql+pymysql://
_raw_db_url = os.getenv("DATABASE_URL", "")

if _raw_db_url.startswith("mysql://"):
    # Konversi otomatis dari format Prisma ke SQLAlchemy
    DATABASE_URL = _raw_db_url.replace("mysql://", "mysql+pymysql://", 1)
elif _raw_db_url.startswith("mysql+pymysql://"):
    DATABASE_URL = _raw_db_url
else:
    raise ValueError(
        "DATABASE_URL tidak valid. "
        "Format yang benar: mysql://user:password@host:3306/dbname"
    )

# ==========================
# TAMBAHAN BARU — JWT
# ==========================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("NEXTAUTH_SECRET", ""))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

if not JWT_SECRET_KEY:
    raise ValueError(
        "JWT_SECRET_KEY tidak ditemukan di .env. "
        "Tambahkan: JWT_SECRET_KEY=your-secret-key"
    )