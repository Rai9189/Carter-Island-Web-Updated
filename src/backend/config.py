import os
from dotenv import load_dotenv

load_dotenv()

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
# Folder rekaman video (.webm). Default: src/backend/recordings. Bisa diarahkan
# ke disk lain lewat .env (mis. SSD eksternal di Jetson); path relatif dihitung
# dari folder backend, bukan dari folder tempat uvicorn dijalankan.
# Dulu tempfile.gettempdir() — /tmp dikosongkan saat reboot → rekaman hilang.
import tempfile
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(_BACKEND_DIR, os.getenv("RECORDINGS_DIR") or "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# Folder lama — hanya dibaca (fallback putar/unduh rekaman sebelum pindah)
LEGACY_RECORDINGS_DIR = tempfile.gettempdir()

# ==========================
# Model Settings
# ==========================
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "16sept.pt")
YOLO_CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.45"))
YOLO_IOU_THRESHOLD = float(os.getenv("YOLO_IOU_THRESHOLD", "0.5"))
YOLO_MAX_DETECTIONS = int(os.getenv("YOLO_MAX_DETECTIONS", "30"))

# ==========================
# Database
# ==========================
_raw_db_url = os.getenv("DATABASE_URL", "")

if _raw_db_url.startswith("mysql://"):
    DATABASE_URL = _raw_db_url.replace("mysql://", "mysql+pymysql://", 1)
elif _raw_db_url.startswith("mysql+pymysql://"):
    DATABASE_URL = _raw_db_url
else:
    raise ValueError(
        "DATABASE_URL tidak valid. "
        "Format yang benar: mysql://user:password@host:3306/dbname"
    )

# ==========================
# JWT
# ==========================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("NEXTAUTH_SECRET", ""))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

if not JWT_SECRET_KEY:
    raise ValueError(
        "JWT_SECRET_KEY tidak ditemukan di .env. "
        "Tambahkan: JWT_SECRET_KEY=your-secret-key"
    )

# ==========================
# Sync ROV → Base Station (SPPI 45-47)
# ==========================
# URL Base Station tempat ROV mengirim data sinkronisasi.
# Kosongkan jika unit ini adalah ROV tanpa target Base Station,
# atau jika unit ini adalah Base Station (receiver).
# Contoh: BASE_STATION_URL=http://192.168.1.10:8000
BASE_STATION_URL = os.getenv("BASE_STATION_URL", "")

# Static shared secret untuk autentikasi ROV -> Base Station (machine-to-machine,
# bukan JWT user). Base Station memverifikasi dengan membandingkan langsung ke
# nilai ini (lihat core/dependencies.py:verify_sync_token) - tidak lewat tabel
# User/expiry seperti JWT biasa. Generate string acak yang panjang dan sama
# persis di kedua sisi (ROV dan Base Station).
BASE_STATION_SYNC_TOKEN = os.getenv("BASE_STATION_SYNC_TOKEN", "")

# Interval pengiriman data sync dalam detik (default 10 detik).
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "10"))