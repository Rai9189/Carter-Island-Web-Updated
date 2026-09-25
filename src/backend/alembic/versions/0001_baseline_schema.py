"""baseline schema

Skema lengkap sesuai models.py per 2026-09-25 (hasil autogenerate).
Tiap tabel hanya dibuat kalau belum ada: DB kosong → skema lengkap; DB lama
yang tabelnya sudah ada dilewati dan diperbaiki oleh revisi 0002.

Revision ID: 0001
Revises: 
Create Date: 2026-09-25 21:18:05.392531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if 'users' not in existing:
        op.create_table('users',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('phone_number', sa.String(length=50), nullable=False),
        sa.Column('role', sa.Enum('USER', 'ADMIN', name='role'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_users_created_at_id', 'users', ['created_at', 'id'], unique=False)
        op.create_index('idx_users_role_created_at_id', 'users', ['role', 'created_at', 'id'], unique=False)
    if 'monitoring_sessions' not in existing:
        op.create_table('monitoring_sessions',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('user_id', sa.String(length=191), nullable=False),
        sa.Column('location_name', sa.String(length=255), nullable=False),
        sa.Column('start_time', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('RUNNING', 'COMPLETED', 'ABORTED', name='sessionstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_sessions_start_time_desc', 'monitoring_sessions', ['start_time'], unique=False)
        op.create_index('idx_sessions_status', 'monitoring_sessions', ['status'], unique=False)
        op.create_index('idx_sessions_user_id', 'monitoring_sessions', ['user_id'], unique=False)
    if 'auv_status' not in existing:
        op.create_table('auv_status',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('session_id', sa.String(length=191), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('roll', sa.Double(), nullable=False),
        sa.Column('pitch', sa.Double(), nullable=False),
        sa.Column('yaw', sa.Double(), nullable=False),
        sa.Column('depth', sa.Double(), nullable=False),
        sa.Column('heading', sa.String(length=50), nullable=False),
        sa.Column('speed', sa.Double(), nullable=False),
        sa.Column('gyroscope', sa.Text(), nullable=True),
        sa.Column('accelerometer', sa.Text(), nullable=True),
        sa.Column('magnetometer', sa.Text(), nullable=True),
        sa.Column('rov_id', sa.String(length=191), nullable=True),
        sa.Column('is_synced', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['monitoring_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_auv_status_is_synced', 'auv_status', ['is_synced'], unique=False)
        op.create_index('idx_auv_status_rov_id', 'auv_status', ['rov_id'], unique=False)
        op.create_index('idx_auv_status_session_id', 'auv_status', ['session_id'], unique=False)
        op.create_index('idx_auv_status_session_timestamp', 'auv_status', ['session_id', 'timestamp'], unique=False)
        op.create_index('idx_auv_status_timestamp_desc', 'auv_status', ['timestamp'], unique=False)
    if 'fish_counts' not in existing:
        op.create_table('fish_counts',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('session_id', sa.String(length=191), nullable=False),
        sa.Column('species_name', sa.String(length=255), nullable=False),
        sa.Column('total_ikan', sa.Integer(), nullable=False),
        sa.Column('waktu_deteksi', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['monitoring_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_fish_counts_session_id', 'fish_counts', ['session_id'], unique=False)
        op.create_index('idx_fish_counts_session_species', 'fish_counts', ['session_id', 'species_name'], unique=False)
        op.create_index('idx_fish_counts_species_name', 'fish_counts', ['species_name'], unique=False)
    if 'telemetries' not in existing:
        op.create_table('telemetries',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('session_id', sa.String(length=191), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('depth', sa.Double(), nullable=False),
        sa.Column('ph_level', sa.Double(), nullable=False),
        sa.Column('tds_value', sa.Double(), nullable=False),
        sa.Column('dissolved_oxygen', sa.Double(), nullable=False),
        sa.Column('water_temp', sa.Double(), nullable=False),
        sa.Column('rov_id', sa.String(length=191), nullable=True),
        sa.Column('is_synced', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['monitoring_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_telemetries_is_synced', 'telemetries', ['is_synced'], unique=False)
        op.create_index('idx_telemetries_rov_id', 'telemetries', ['rov_id'], unique=False)
        op.create_index('idx_telemetries_session_id', 'telemetries', ['session_id'], unique=False)
        op.create_index('idx_telemetries_session_timestamp', 'telemetries', ['session_id', 'timestamp'], unique=False)
        op.create_index('idx_telemetries_timestamp_desc', 'telemetries', ['timestamp'], unique=False)
    if 'video_paths' not in existing:
        op.create_table('video_paths',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('session_id', sa.String(length=191), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('format', sa.String(length=50), nullable=False),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['monitoring_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_video_paths_created_desc', 'video_paths', ['created_at'], unique=False)
        op.create_index('idx_video_paths_file_name', 'video_paths', ['file_name'], unique=False)
        op.create_index('idx_video_paths_session_id', 'video_paths', ['session_id'], unique=False)
    if 'video_stream' not in existing:
        op.create_table('video_stream',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('session_id', sa.String(length=191), nullable=False),
        sa.Column('stream_url', sa.Text(), nullable=False),
        sa.Column('format', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['monitoring_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_video_stream_session_id', 'video_stream', ['session_id'], unique=False)
        op.create_index('idx_video_stream_timestamp_desc', 'video_stream', ['timestamp'], unique=False)
    if 'detections' not in existing:
        op.create_table('detections',
        sa.Column('id', sa.String(length=191), nullable=False),
        sa.Column('session_id', sa.String(length=191), nullable=False),
        sa.Column('telemetry_id', sa.String(length=191), nullable=True),
        sa.Column('species_name', sa.String(length=255), nullable=False),
        sa.Column('confidence', sa.Double(), nullable=False),
        sa.Column('depth_at_detection', sa.Double(), nullable=True),
        sa.Column('frame_number', sa.Integer(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('rov_id', sa.String(length=191), nullable=True),
        sa.Column('is_synced', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['monitoring_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['telemetry_id'], ['telemetries.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        mysql_engine='InnoDB'
        )
        op.create_index('idx_detections_detected_at_desc', 'detections', ['detected_at'], unique=False)
        op.create_index('idx_detections_is_synced', 'detections', ['is_synced'], unique=False)
        op.create_index('idx_detections_rov_id', 'detections', ['rov_id'], unique=False)
        op.create_index('idx_detections_session_id', 'detections', ['session_id'], unique=False)
        op.create_index('idx_detections_session_species', 'detections', ['session_id', 'species_name'], unique=False)
        op.create_index('idx_detections_species_name', 'detections', ['species_name'], unique=False)
        op.create_index('idx_detections_telemetry_id', 'detections', ['telemetry_id'], unique=False)


def downgrade() -> None:
    # Sengaja tidak didukung: downgrade baseline = DROP semua tabel beserta datanya.
    raise NotImplementedError("Downgrade baseline tidak didukung (akan menghapus semua data)")
