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
    Terapkan migrasi Alembic sampai revisi terbaru (alembic upgrade head).
    DB kosong → dibuat lengkap; DB lama → kolom/index diperbaiki tanpa hapus data
    (lihat alembic/versions). Dipanggil saat startup FastAPI & seed.py.

    Dulu Base.metadata.create_all() — hanya membuat tabel yang belum ada,
    tidak pernah mengubah tabel lama, jadi DB lama (mis. Jetson) tertinggal.
    """
    try:
        import os
        from alembic import command
        from alembic.config import Config

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        alembic_cfg.attributes["configure_logger"] = False  # jangan timpa logging backend
        command.upgrade(alembic_cfg, "head")
        logger.info("Database schema up to date (alembic upgrade head)")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise