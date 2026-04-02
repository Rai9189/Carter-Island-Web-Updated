"""
SQLAlchemy models — 1:1 dari schema.prisma.

Semua nama tabel, kolom, dan index sama persis dengan Prisma
sehingga data lama tetap bisa dibaca tanpa migrasi apapun.

Mapping Prisma → SQLAlchemy:
  String       → String
  Int          → Integer
  Float        → Float
  Boolean      → Boolean
  DateTime     → DateTime
  BigInt       → BigInteger
  String @db.Text → Text
  enum Role    → Enum('USER', 'ADMIN')
  @id @default(cuid()) → String primary key (cuid dibuat manual)
  @default(now()) → server_default=func.now()
  @updatedAt   → onupdate=func.now()
"""
import enum
from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, BigInteger,
    Text, Enum, ForeignKey, Index, func
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from typing import Optional, List

from database.connection import Base
from core.cuid import generate_cuid


# ==========================
# Enum Role (sama dengan Prisma)
# ==========================
class Role(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


# ==========================
# Model: users
# @@map("users")
# ==========================
class User(Base):
    __tablename__ = "users"

    # @id @default(cuid())
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_cuid
    )
    # fullName String @map("full_name")
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # email String @unique
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    # password String
    password: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # phoneNumber String @map("phone_number")
    phone_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # role Role @default(USER)
    role: Mapped[Role] = mapped_column(
        Enum(Role), nullable=False, default=Role.USER
    )
    # createdAt DateTime @default(now()) @map("created_at")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # updatedAt DateTime @updatedAt @map("updated_at")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # @@index([createdAt, id], map: "idx_users_created_at_id")
        Index("idx_users_created_at_id", "created_at", "id"),
        # @@index([role, createdAt, id], map: "idx_users_role_created_at_id")
        Index("idx_users_role_created_at_id", "role", "created_at", "id"),
        # @@index([createdAt(sort: Desc), id(sort: Desc)])
        Index("idx_users_created_desc_id_desc", "created_at", "id"),
    )

    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role}>"


# ==========================
# Model: fish_detections
# @@map("fish_detections")
# ==========================
class FishDetection(Base):
    __tablename__ = "fish_detections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_cuid
    )
    # sessionId String? @map("session_id")
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    # timestamp DateTime @default(now())
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # fishCount Int @map("fish_count")
    fish_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    # frameNumber Int? @map("frame_number")
    frame_number: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    # imageUrl String? @map("image_url") @db.Text
    image_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

    # Relasi ke DetectionDetail
    detection_details: Mapped[List["DetectionDetail"]] = relationship(
        "DetectionDetail",
        back_populates="detection",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_detections_timestamp", "timestamp"),
        Index("idx_detections_session_timestamp", "session_id", "timestamp"),
        Index("idx_detections_created_desc", "created_at"),
    )

    def __repr__(self):
        return f"<FishDetection id={self.id} fish_count={self.fish_count}>"


# ==========================
# Model: detection_details
# @@map("detection_details")
# ==========================
class DetectionDetail(Base):
    __tablename__ = "detection_details"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_cuid
    )
    # detectionId String @map("detection_id")
    detection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("fish_detections.id", ondelete="CASCADE"),
        nullable=False,
    )
    # className String @map("class_name")
    class_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # confidence Float
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    # boundingBoxX1 Float @map("bbox_x1")
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    # boundingBoxY1 Float @map("bbox_y1")
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    # boundingBoxX2 Float @map("bbox_x2")
    bbox_x2: Mapped[float] = mapped_column(Float, nullable=False)
    # boundingBoxY2 Float @map("bbox_y2")
    bbox_y2: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relasi ke FishDetection
    detection: Mapped["FishDetection"] = relationship(
        "FishDetection", back_populates="detection_details"
    )

    __table_args__ = (
        Index("idx_details_detection_id", "detection_id"),
        Index("idx_details_class_name", "class_name"),
        Index("idx_details_confidence_desc", "confidence"),
    )

    def __repr__(self):
        return f"<DetectionDetail id={self.id} class={self.class_name} conf={self.confidence}>"


# ==========================
# Model: recordings
# @@map("recordings")
# ==========================
class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_cuid
    )
    # sessionId String @map("session_id")
    session_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # filename String
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # filepath String @db.Text
    filepath: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    # fileSize BigInt @map("file_size")
    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    # duration Float
    duration: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    # startTime DateTime @map("start_time")
    start_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )
    # endTime DateTime @map("end_time")
    end_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_recordings_session_id", "session_id"),
        Index("idx_recordings_start_time_desc", "start_time"),
        Index("idx_recordings_created_desc", "created_at"),
    )

    def __repr__(self):
        return f"<Recording id={self.id} filename={self.filename}>"


# ==========================
# Model: telemetry
# @@map("telemetry")
# ==========================
class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_cuid
    )
    # Attitude
    roll_deg: Mapped[float] = mapped_column(Float, nullable=False)
    pitch_deg: Mapped[float] = mapped_column(Float, nullable=False)
    yaw_deg: Mapped[float] = mapped_column(Float, nullable=False)
    # Compass
    heading_deg: Mapped[float] = mapped_column(Float, nullable=False)
    # Battery
    voltage_v: Mapped[float] = mapped_column(Float, nullable=False)
    current_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remaining_percent: Mapped[float] = mapped_column(Float, nullable=False)
    consumed_mah: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Health
    gyro_cal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accel_cal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mag_cal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Metadata
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_telemetry_timestamp_desc", "timestamp"),
        Index("idx_telemetry_created_desc", "created_at"),
    )

    def __repr__(self):
        return f"<Telemetry id={self.id} battery={self.remaining_percent}%>"


# ==========================
# Model: auv_status
# @@map("auv_status")
# ==========================
class AUVStatus(Base):
    __tablename__ = "auv_status"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_cuid
    )
    # isOnline Boolean @map("is_online")
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # connectionStrength String @map("connection_strength")
    connection_strength: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # uptimeSeconds Int @map("uptime_seconds")
    uptime_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # locationStatus String @default("Active") @map("location_status")
    location_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Active"
    )
    # lastStreamTime DateTime? @map("last_stream_time")
    last_stream_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_auv_status_timestamp_desc", "timestamp"),
        Index("idx_auv_status_created_desc", "created_at"),
    )

    def __repr__(self):
        return f"<AUVStatus id={self.id} online={self.is_online}>"