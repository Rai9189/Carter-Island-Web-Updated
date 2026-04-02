"""
Database connection configuration menggunakan SQLAlchemy.
Menggantikan Prisma ORM yang sebelumnya ada di sisi Next.js.
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool

from config import DATABASE_URL

logger = logging.getLogger("carter-backend")


# ==========================
# Base class untuk semua model
# ==========================
class Base(DeclarativeBase):
    pass


# ==========================
# Engine MySQL
# ==========================
# DATABASE_URL format: mysql+pymysql://user:password@host:port/dbname
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # Jumlah koneksi yang dipertahankan
    max_overflow=20,        # Koneksi tambahan saat pool penuh
    pool_pre_ping=True,     # Cek koneksi sebelum dipakai (hindari stale connection)
    pool_recycle=3600,      # Recycle koneksi tiap 1 jam
    echo=False,             # Set True untuk debug SQL query
)


# ==========================
# Session factory
# ==========================
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ==========================
# Dependency untuk FastAPI
# ==========================
def get_db():
    """
    FastAPI dependency untuk mendapatkan DB session.
    Dipakai dengan Depends(get_db) di setiap route.

    Contoh pemakaian:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================
# Utility functions
# ==========================
def check_db_connection() -> bool:
    """
    Cek apakah koneksi ke database berhasil.
    Dipakai saat startup untuk verifikasi.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection: OK")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def init_db():
    """
    Buat semua tabel yang belum ada.
    TIDAK menghapus tabel yang sudah ada (safe untuk data lama).
    Dipanggil saat startup FastAPI.
    """
    try:
        # Import models agar Base mengetahui semua tabel
        from database import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise