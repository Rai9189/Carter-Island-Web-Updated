"""
Konfigurasi Alembic — migrasi skema MySQL.

Koneksi memakai engine & DATABASE_URL yang sama dengan backend
(database/connection.py, config.py), jadi tidak ada URL di alembic.ini.

Migrasi dijalankan otomatis saat backend start (database/connection.py
init_db → upgrade head). Manual dari folder src/backend:
    alembic upgrade head      # terapkan semua migrasi
    alembic current           # revisi DB saat ini
    alembic check             # cek models.py vs DB (tidak ada perubahan tertunda)
    alembic revision --autogenerate -m "pesan"   # buat migrasi baru dari models.py
"""
from logging.config import fileConfig

from alembic import context

from database.connection import Base, engine
from database import models  # noqa: F401 — daftarkan semua tabel ke Base.metadata

config = context.config

# Dari CLI: pakai logging alembic.ini. Dari init_db (startup) logging
# backend/uvicorn sudah diatur — jangan ditimpa.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Cetak SQL tanpa koneksi DB (alembic upgrade head --sql)."""
    context.configure(
        url=engine.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
