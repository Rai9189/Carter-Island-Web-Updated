"""
SQLAlchemy models — sesuai dokumen C300 ROV El Torpedo V3.

PENTING — Kompatibilitas dengan tabel users lama (Prisma):
  Tabel users yang sudah ada menggunakan:
    - VARCHAR(191) — bukan VARCHAR(36)
    - COLLATE utf8mb4_unicode_ci
    - ENGINE=InnoDB
  Semua tabel baru harus menggunakan konfigurasi yang sama
  agar Foreign Key ke users.id tidak ditolak MySQL (error 3780).

Struktur tabel sesuai ERD dokumen C300.02TA2026:
  - users               : akun pengguna & hak akses (RBAC) — tidak diubah
  - monitoring_sessions : tabel sentral sesi misi
  - telemetries         : data kualitas air (pH, TDS, DO, suhu, depth)
  - auv_status          : data navigasi & attitude ROV
  - detections          : hasil identifikasi spesies ikan YOLOv8
  - fish_counts         : agregasi jumlah populasi ikan per sesi
  - video_paths         : metadata arsip rekaman video
  - video_stream        : konfigurasi akses live streaming WebRTC

Perubahan v2 — SPPI 45/46/47 Sync ROV → Base Station:
  - Tambah kolom `rov_id`    di Telemetry, Detection, AUVStatus
  - Tambah kolom `is_synced` di Telemetry, Detection, AUVStatus

Perubahan v3 — Sinkronisasi ERD:
  - users.full_name      → users.username
  - fish_counts.total_count  → fish_counts.total_ikan
  - fish_counts.detected_at  → fish_counts.waktu_deteksi
"""

import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Float, Double, Boolean, DateTime,
    BigInteger, Text, Enum, ForeignKey, Index, func
)
from sqlalchemy.orm import relationship, mapped_column, Mapped

from database.connection import Base
from core.cuid import generate_cuid

# ── Konstanta tipe kolom ─────────────────────────────────────
STR191 = String(191)
STR255 = String(255)
STR50  = String(50)

MYSQL_OPTS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
    "mysql_engine":  "InnoDB",
}


# ==========================
# Enum Role
# ==========================
class Role(str, enum.Enum):
    USER  = "USER"
    ADMIN = "ADMIN"


# ==========================
# Enum SessionStatus
# ==========================
class SessionStatus(str, enum.Enum):
    RUNNING   = "Running"
    COMPLETED = "Completed"
    ABORTED   = "Aborted"


# ============================================================
# Model: users
# ============================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    username: Mapped[str] = mapped_column(STR255, nullable=False)           # ← ganti dari full_name
    email: Mapped[str] = mapped_column(STR255, nullable=False, unique=True)
    password: Mapped[str] = mapped_column(STR255, nullable=False)
    phone_number: Mapped[str] = mapped_column(STR50, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.USER)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[List["MonitoringSession"]] = relationship(
        "MonitoringSession", back_populates="user"
    )

    __table_args__ = (
        Index("idx_users_created_at_id", "created_at", "id"),
        Index("idx_users_role_created_at_id", "role", "created_at", "id"),
        {"extend_existing": True, **MYSQL_OPTS},
    )

    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role}>"


# ============================================================
# Model: monitoring_sessions
# ============================================================
class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(
        STR191, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    location_name: Mapped[str] = mapped_column(STR255, nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.RUNNING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")
    telemetries: Mapped[List["Telemetry"]] = relationship(
        "Telemetry", back_populates="session", cascade="all, delete-orphan"
    )
    auv_statuses: Mapped[List["AUVStatus"]] = relationship(
        "AUVStatus", back_populates="session", cascade="all, delete-orphan"
    )
    detections: Mapped[List["Detection"]] = relationship(
        "Detection", back_populates="session", cascade="all, delete-orphan"
    )
    fish_counts: Mapped[List["FishCount"]] = relationship(
        "FishCount", back_populates="session", cascade="all, delete-orphan"
    )
    video_paths: Mapped[List["VideoPath"]] = relationship(
        "VideoPath", back_populates="session", cascade="all, delete-orphan"
    )
    video_streams: Mapped[List["VideoStream"]] = relationship(
        "VideoStream", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sessions_user_id", "user_id"),
        Index("idx_sessions_status", "status"),
        Index("idx_sessions_start_time_desc", "start_time"),
        MYSQL_OPTS,
    )

    def __repr__(self):
        return f"<MonitoringSession id={self.id} location={self.location_name} status={self.status}>"


# ============================================================
# Model: telemetries
# Data kualitas air: pH, TDS, Dissolved Oxygen, suhu, kedalaman.
#
# Kolom sync (SPPI-45):
#   rov_id    — ID asli dari DB ROV, diisi Base Station untuk dedup
#   is_synced — False = belum dikirim ke Base Station (default di ROV)
#               True  = sudah berhasil dikirim/diterima
# ============================================================
class Telemetry(Base):
    __tablename__ = "telemetries"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    session_id: Mapped[str] = mapped_column(
        STR191,
        ForeignKey("monitoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    depth: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    ph_level: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    tds_value: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    dissolved_oxygen: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    water_temp: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    # ── Sync columns ─────────────────────────────────────────
    rov_id: Mapped[Optional[str]] = mapped_column(STR191, nullable=True)
    is_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # ─────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    session: Mapped["MonitoringSession"] = relationship(
        "MonitoringSession", back_populates="telemetries"
    )
    detections: Mapped[List["Detection"]] = relationship(
        "Detection", back_populates="telemetry"
    )

    __table_args__ = (
        Index("idx_telemetries_session_id", "session_id"),
        Index("idx_telemetries_timestamp_desc", "timestamp"),
        Index("idx_telemetries_session_timestamp", "session_id", "timestamp"),
        Index("idx_telemetries_is_synced", "is_synced"),
        Index("idx_telemetries_rov_id", "rov_id"),
        MYSQL_OPTS,
    )

    def __repr__(self):
        return (
            f"<Telemetry id={self.id} ph={self.ph_level} "
            f"tds={self.tds_value} do={self.dissolved_oxygen} "
            f"temp={self.water_temp} depth={self.depth}>"
        )


# ============================================================
# Model: auv_status
# Data navigasi & attitude ROV dari IMU Pixhawk.
#
# Kolom sync (SPPI-47):
#   rov_id    — ID asli dari DB ROV, diisi Base Station untuk dedup
#   is_synced — False = belum dikirim ke Base Station (default di ROV)
# ============================================================
class AUVStatus(Base):
    __tablename__ = "auv_status"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    session_id: Mapped[str] = mapped_column(
        STR191,
        ForeignKey("monitoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    roll: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    pitch: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    yaw: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    depth: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    heading: Mapped[str] = mapped_column(STR50, nullable=False, default="N")
    speed: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    gyroscope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accelerometer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    magnetometer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ── Sync columns ─────────────────────────────────────────
    rov_id: Mapped[Optional[str]] = mapped_column(STR191, nullable=True)
    is_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # ─────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    session: Mapped["MonitoringSession"] = relationship(
        "MonitoringSession", back_populates="auv_statuses"
    )

    __table_args__ = (
        Index("idx_auv_status_session_id", "session_id"),
        Index("idx_auv_status_timestamp_desc", "timestamp"),
        Index("idx_auv_status_session_timestamp", "session_id", "timestamp"),
        Index("idx_auv_status_is_synced", "is_synced"),
        Index("idx_auv_status_rov_id", "rov_id"),
        MYSQL_OPTS,
    )

    def __repr__(self):
        return (
            f"<AUVStatus id={self.id} roll={self.roll} "
            f"pitch={self.pitch} yaw={self.yaw} depth={self.depth}>"
        )


# ============================================================
# Model: detections
# Hasil identifikasi spesies ikan oleh YOLOv8.
#
# Kolom sync (SPPI-46):
#   rov_id    — ID asli dari DB ROV, diisi Base Station untuk dedup
#   is_synced — False = belum dikirim ke Base Station (default di ROV)
# ============================================================
class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    session_id: Mapped[str] = mapped_column(
        STR191,
        ForeignKey("monitoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    telemetry_id: Mapped[Optional[str]] = mapped_column(
        STR191,
        ForeignKey("telemetries.id", ondelete="SET NULL"),
        nullable=True,
    )
    species_name: Mapped[str] = mapped_column(STR255, nullable=False)
    confidence: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    depth_at_detection: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    frame_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # ── Sync columns ─────────────────────────────────────────
    rov_id: Mapped[Optional[str]] = mapped_column(STR191, nullable=True)
    is_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # ─────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    session: Mapped["MonitoringSession"] = relationship(
        "MonitoringSession", back_populates="detections"
    )
    telemetry: Mapped[Optional["Telemetry"]] = relationship(
        "Telemetry", back_populates="detections"
    )

    __table_args__ = (
        Index("idx_detections_session_id", "session_id"),
        Index("idx_detections_telemetry_id", "telemetry_id"),
        Index("idx_detections_species_name", "species_name"),
        Index("idx_detections_detected_at_desc", "detected_at"),
        Index("idx_detections_session_species", "session_id", "species_name"),
        Index("idx_detections_is_synced", "is_synced"),
        Index("idx_detections_rov_id", "rov_id"),
        MYSQL_OPTS,
    )

    def __repr__(self):
        return (
            f"<Detection id={self.id} species={self.species_name} "
            f"conf={self.confidence:.2f} depth={self.depth_at_detection}>"
        )


# ============================================================
# Model: fish_counts
# ============================================================
class FishCount(Base):
    __tablename__ = "fish_counts"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    session_id: Mapped[str] = mapped_column(
        STR191,
        ForeignKey("monitoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    species_name: Mapped[str] = mapped_column(STR255, nullable=False)
    total_ikan: Mapped[int] = mapped_column(Integer, nullable=False, default=0)       # ← ganti dari total_count
    waktu_deteksi: Mapped[datetime] = mapped_column(                                   # ← ganti dari detected_at
        DateTime, nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    session: Mapped["MonitoringSession"] = relationship(
        "MonitoringSession", back_populates="fish_counts"
    )

    __table_args__ = (
        Index("idx_fish_counts_session_id", "session_id"),
        Index("idx_fish_counts_species_name", "species_name"),
        Index("idx_fish_counts_session_species", "session_id", "species_name"),
        MYSQL_OPTS,
    )

    def __repr__(self):
        return f"<FishCount id={self.id} species={self.species_name} total={self.total_ikan}>"


# ============================================================
# Model: video_paths
# ============================================================
class VideoPath(Base):
    __tablename__ = "video_paths"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    session_id: Mapped[str] = mapped_column(
        STR191,
        ForeignKey("monitoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(STR255, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    format: Mapped[str] = mapped_column(STR50, nullable=False, default="mp4")
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    session: Mapped["MonitoringSession"] = relationship(
        "MonitoringSession", back_populates="video_paths"
    )

    __table_args__ = (
        Index("idx_video_paths_session_id", "session_id"),
        Index("idx_video_paths_created_desc", "created_at"),
        Index("idx_video_paths_file_name", "file_name"),
        MYSQL_OPTS,
    )

    def __repr__(self):
        return (
            f"<VideoPath id={self.id} file={self.file_name} "
            f"size={self.file_size} format={self.format}>"
        )


# ============================================================
# Model: video_stream
# ============================================================
class VideoStream(Base):
    __tablename__ = "video_stream"

    id: Mapped[str] = mapped_column(STR191, primary_key=True, default=generate_cuid)
    session_id: Mapped[str] = mapped_column(
        STR191,
        ForeignKey("monitoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    stream_url: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(STR50, nullable=False, default="WebRTC")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    session: Mapped["MonitoringSession"] = relationship(
        "MonitoringSession", back_populates="video_streams"
    )

    __table_args__ = (
        Index("idx_video_stream_session_id", "session_id"),
        Index("idx_video_stream_timestamp_desc", "timestamp"),
        MYSQL_OPTS,
    )

    def __repr__(self):
        return f"<VideoStream id={self.id} url={self.stream_url} format={self.format}>"