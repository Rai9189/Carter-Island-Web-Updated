"""upgrade legacy schema

Perbaiki DB yang dibuat dengan models.py versi lama, karena create_all() dulu
tidak pernah mengubah tabel yang sudah ada:
  - sebelum 655ef51 (2026-05-12): belum ada kolom rov_id & is_synced (+ index)
    di telemetries, auv_status, detections → sync SPPI error
  - sebelum d71bed5 (2026-09-24): users.full_name, fish_counts.total_count,
    fish_counts.detected_at → sekarang username, total_ikan, waktu_deteksi

Setiap langkah cek kondisi dulu — DB yang sudah sesuai tidak diubah.
Data lama dipertahankan; baris lama dapat is_synced = False (belum pernah
terkirim, karena sync sebelumnya tidak pernah berhasil).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25 21:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabel, nama lama, nama baru, kwargs alter_column untuk MySQL CHANGE COLUMN)
RENAMES = [
    ('users', 'full_name', 'username',
     dict(existing_type=sa.String(length=255), existing_nullable=False)),
    ('fish_counts', 'total_count', 'total_ikan',
     dict(existing_type=sa.Integer(), existing_nullable=False)),
    ('fish_counts', 'detected_at', 'waktu_deteksi',
     dict(existing_type=sa.DateTime(), existing_nullable=False,
          existing_server_default=sa.text('CURRENT_TIMESTAMP'))),
]

SYNC_TABLES = ['telemetries', 'auv_status', 'detections']


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    def columns(table):
        return {c['name'] for c in insp.get_columns(table)}

    for table, old, new, kwargs in RENAMES:
        cols = columns(table)
        if old in cols and new not in cols:
            op.alter_column(table, old, new_column_name=new, **kwargs)

    for table in SYNC_TABLES:
        cols = columns(table)
        if 'rov_id' not in cols:
            op.add_column(table, sa.Column('rov_id', sa.String(length=191), nullable=True))
        if 'is_synced' not in cols:
            # server_default hanya untuk mengisi baris lama, lalu dilepas
            # supaya sama dengan skema baseline (default diisi ORM)
            op.add_column(table, sa.Column('is_synced', sa.Boolean(), nullable=False,
                                           server_default=sa.false()))
            op.alter_column(table, 'is_synced', server_default=None,
                            existing_type=sa.Boolean(), existing_nullable=False)

        indexes = {i['name'] for i in insp.get_indexes(table)}
        for column in ('is_synced', 'rov_id'):
            name = f'idx_{table}_{column}'
            if name not in indexes:
                op.create_index(name, table, [column], unique=False)


def downgrade() -> None:
    # Tidak dikembalikan ke skema lama — kode sekarang tidak bisa jalan dengannya.
    pass
