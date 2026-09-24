"""
Seed script — Carter Island AUV Database
Jalankan dari folder src/backend/:
    python seed.py

Akan membuat:
  - 2 user (1 ADMIN, 1 USER)
  - 6 monitoring sessions (Completed)
  - Telemetry data per session
  - AUV status per session
  - Detections per session
  - Fish counts per session
  - Video paths per session
"""

import sys
import os
import random
from datetime import datetime, timezone, timedelta

# Pastikan path backend bisa diimport
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_db, init_db, check_db_connection
from database.models import (
    User, MonitoringSession, Telemetry, AUVStatus,
    Detection, FishCount, VideoPath, Role, SessionStatus
)
from core.cuid import generate_cuid
from auth.password import hash_password

# ── Config ────────────────────────────────────────────────────────────────────

SPECIES = ['Kerapu', 'Bandeng', 'Teri', 'Unknown']
HEADINGS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
LOCATIONS = [
    'Survei Laut', 'Survei Semarang', 'Survei Yogya',
    'Survei Solo', 'Survei Jakarta', 'Survei Bali'
]

# Sessions: (location, days_ago, duration_hours, duration_minutes)
SESSION_CONFIGS = [
    ('Survei Bali',     49, 1, 45),
    ('Survei Jakarta',  42, 2, 30),
    ('Survei Solo',     36, 3,  0),
    ('Survei Yogya',    30, 1, 50),
    ('Survei Semarang', 20, 2, 15),
    ('Survei Laut',      0, 0, 42),  # paling baru
]


def rnd(a: float, b: float, decimals: int = 2) -> float:
    return round(random.uniform(a, b), decimals)


def make_timestamp(base: datetime, offset_minutes: int) -> datetime:
    return base + timedelta(minutes=offset_minutes)


# ── Main Seed ─────────────────────────────────────────────────────────────────

def seed():
    if not check_db_connection():
        print("❌ Tidak bisa konek ke database! Periksa DATABASE_URL di .env")
        sys.exit(1)

    init_db()
    db = next(get_db())

    print("🌱 Mulai seeding database Carter Island...\n")

    # ── 1. Users ──────────────────────────────────────────────────────────────
    print("👤 Membuat users...")

    existing_admin = db.query(User).filter(User.email == 'admin@carterisland.com').first()
    existing_user  = db.query(User).filter(User.email == 'user@carterisland.com').first()

    if existing_admin:
        admin = existing_admin
        print(f"   ↳ Admin sudah ada: {admin.email}")
    else:
        admin = User(
            id=generate_cuid(),
            username='Carter Island Administrator',
            email='admin@carterisland.com',
            password=hash_password('admin123456'),
            phone_number='+62-812-3456-7890',
            role=Role.ADMIN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        print(f"   ✅ Admin dibuat: {admin.email} / admin123456")

    if existing_user:
        user = existing_user
        print(f"   ↳ User sudah ada: {user.email}")
    else:
        user = User(
            id=generate_cuid(),
            username='Carter Island User',
            email='user@carterisland.com',
            password=hash_password('user123456'),
            phone_number='+62-812-3456-7891',
            role=Role.USER,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        print(f"   ✅ User dibuat: {user.email} / user123456")

    db.flush()

    # ── 2. Sessions + data per session ───────────────────────────────────────
    print("\n📋 Membuat monitoring sessions...")
    now = datetime.now(timezone.utc)

    for loc, days_ago, dur_h, dur_m in SESSION_CONFIGS:
        start = now - timedelta(days=days_ago, hours=8)
        start = start.replace(hour=random.choice([6, 7, 8, 9]), minute=random.choice([0, 30]), second=0, microsecond=0)
        duration_secs = dur_h * 3600 + dur_m * 60
        end = start + timedelta(seconds=duration_secs) if duration_secs > 0 else None
        status = SessionStatus.COMPLETED if end else SessionStatus.RUNNING

        session = MonitoringSession(
            id=generate_cuid(),
            user_id=admin.id,
            location_name=loc,
            start_time=start,
            end_time=end,
            status=status,
            created_at=start,
            updated_at=end or now,
        )
        db.add(session)
        db.flush()

        print(f"   ✅ Session: {loc} ({start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%H:%M') if end else 'running'}, {dur_h}j {dur_m}m)")

        # ── Telemetry (1 per 5 menit) ────────────────────────────────────────
        n_telemetry = max(1, duration_secs // 300) if duration_secs > 0 else 8
        tel_ids = []
        for i in range(n_telemetry):
            t = make_timestamp(start, i * 5)
            tel = Telemetry(
                id=generate_cuid(),
                session_id=session.id,
                timestamp=t,
                depth=rnd(1.5, 5.0),
                ph_level=rnd(7.2, 8.4),
                tds_value=rnd(280, 380),
                dissolved_oxygen=rnd(4.5, 8.5),
                water_temp=rnd(26.0, 30.5),
                is_synced=False,
                created_at=t,
            )
            db.add(tel)
            tel_ids.append(tel.id)
        db.flush()

        # ── AUV Status (1 per 2 menit) ───────────────────────────────────────
        n_auv = max(1, duration_secs // 120) if duration_secs > 0 else 20
        for i in range(n_auv):
            t = make_timestamp(start, i * 2)
            auv = AUVStatus(
                id=generate_cuid(),
                session_id=session.id,
                timestamp=t,
                roll=rnd(-5.0, 5.0),
                pitch=rnd(-3.0, 3.0),
                yaw=rnd(0.0, 360.0),
                depth=rnd(1.5, 5.0),
                heading=random.choice(HEADINGS),
                speed=rnd(0.5, 3.5),
                gyroscope='{"x":0.01,"y":0.02,"z":0.0}',
                accelerometer='{"x":0.0,"y":0.0,"z":9.8}',
                magnetometer='{"x":25.0,"y":3.0,"z":-42.0}',
                is_synced=False,
                created_at=t,
            )
            db.add(auv)
        db.flush()

        # ── Detections ───────────────────────────────────────────────────────
        n_detections = random.randint(8, 15)
        species_in_session = random.sample(SPECIES, random.randint(2, 4))

        for i in range(n_detections):
            offset = random.randint(1, max(1, duration_secs // 60)) if duration_secs > 0 else random.randint(1, 40)
            t = make_timestamp(start, offset)
            tel_id = random.choice(tel_ids) if tel_ids else None
            det = Detection(
                id=generate_cuid(),
                session_id=session.id,
                telemetry_id=tel_id,
                species_name=random.choice(species_in_session),
                confidence=rnd(0.62, 0.97),
                depth_at_detection=rnd(1.5, 5.0),
                frame_number=random.randint(100, 2000),
                detected_at=t,
                is_synced=False,
                created_at=t,
            )
            db.add(det)
        db.flush()

        # ── Fish Counts (agregasi per spesies) ───────────────────────────────
        species_counts: dict = {}
        for sp in species_in_session:
            species_counts[sp] = random.randint(1, 8)

        for sp, cnt in species_counts.items():
            fc = FishCount(
                id=generate_cuid(),
                session_id=session.id,
                species_name=sp,
                total_ikan=cnt,
                waktu_deteksi=start,
                created_at=start,
                updated_at=end or now,
            )
            db.add(fc)

        # ── Video Path ───────────────────────────────────────────────────────
        file_name = f"{loc.replace(' ', '_').lower()}_{start.strftime('%Y%m%d')}.mp4"
        file_size = random.randint(40, 320) * 1024 * 1024  # 40–320 MB
        vp = VideoPath(
            id=generate_cuid(),
            session_id=session.id,
            file_name=file_name,
            file_path=f"/recordings/{file_name}",
            file_size=file_size,
            format='mp4',
            duration=float(duration_secs) if duration_secs > 0 else None,
            created_at=start,
            updated_at=end or now,
        )
        db.add(vp)

        db.flush()

    # ── Commit semua ──────────────────────────────────────────────────────────
    db.commit()

    print("\n✅ Seeding selesai!")
    print("=" * 50)
    print("📌 Akun login:")
    print("   Admin : admin@carterisland.com / admin123456")
    print("   User  : user@carterisland.com  / user123456")
    print("=" * 50)
    print(f"   Sessions : {len(SESSION_CONFIGS)} sesi")
    print(f"   Locations: {', '.join(l for l, *_ in SESSION_CONFIGS)}")
    print("=" * 50)


if __name__ == '__main__':
    seed()