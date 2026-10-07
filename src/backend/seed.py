"""
Seed script — Carter Island AUV Database
Jalankan dari folder src/backend/:
    python seed.py            # tambah data contoh
    python seed.py --reset    # hapus dulu misi seed lama (nama di SESSION_CONFIGS), lalu isi ulang

Akan membuat:
  - 2 user (1 ADMIN, 1 USER)
  - 7 monitoring sessions (Completed, 1 sengaja kosong)
  - Telemetry data per session
  - AUV status per session
  - Detections per session
  - Fish counts per session (dihitung dari detections)
  - Video paths per session (klip dummy .webm di RECORDINGS_DIR)
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
    Detection, VideoPath, Role, SessionStatus
)
from database.crud.fish_counts import recompute_fish_counts
from config import RECORDINGS_DIR
from routers.recordings import delete_recording_files
from core.cuid import generate_cuid
import cv2
import numpy as np
from auth.password import hash_password

# ── Config ────────────────────────────────────────────────────────────────────

# Harus sama persis dengan nama kelas model YOLO (lihat T8)
SPECIES = ['Kerapu', 'Bandeng', 'Nila Salin', 'Bawal Bintang']
HEADINGS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

# Misi milik akun USER (sisanya milik ADMIN)
USER_LOCATIONS = {'Survei Yogya', 'Survei Semarang'}

# Sessions: (location, days_ago, duration_hours, duration_minutes, kosong)
# kosong=True → tanpa telemetri/deteksi/rekaman, untuk uji tampilan "No Data"
SESSION_CONFIGS = [
    ('Survei Bali',     49, 1, 45, False),
    ('Survei Jakarta',  42, 2, 30, False),
    ('Survei Solo',     36, 3,  0, False),
    ('Survei Yogya',    30, 1, 50, False),
    ('Survei Semarang', 20, 2, 15, False),
    ('Survei Kosong',   10, 0, 30, True),
    ('Survei Laut',      0, 0, 42, False),  # paling baru
]


def rnd(a: float, b: float, decimals: int = 2) -> float:
    return round(random.uniform(a, b), decimals)


def make_timestamp(base: datetime, offset_minutes: int) -> datetime:
    return base + timedelta(minutes=offset_minutes)


def make_dummy_video(path: str, label: str, seconds: int = 10, fps: int = 10) -> None:
    """Klip .webm kecil (VP80, sama dengan perekam asli) supaya putar/unduh/hapus bisa diuji."""
    writer = cv2.VideoWriter(path, cv2.VideoWriter.fourcc(*'VP80'), fps, (320, 240))
    for i in range(seconds * fps):
        frame = np.full((240, 320, 3), (90, 60, 20), np.uint8)
        cv2.putText(frame, label, (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"{i / fps:4.1f}s", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()


def reset_seed_sessions(db) -> None:
    """
    Hapus misi seed lama berdasarkan nama misi di SESSION_CONFIGS — bukan
    berdasarkan akun, supaya misi uji asli milik akun seed tidak ikut hilang.
    Telemetri/deteksi/fish count/rekaman ikut terhapus lewat cascade; file
    video dihapus setelah commit (pola sama dengan DELETE /api/sessions).
    """
    names = [loc for loc, *_ in SESSION_CONFIGS]
    sessions = db.query(MonitoringSession).filter(MonitoringSession.location_name.in_(names)).all()
    file_names = [v.file_name for s in sessions for v in s.video_paths]
    for s in sessions:
        db.delete(s)
    db.commit()
    delete_recording_files(file_names)
    print(f"🧹 Reset: {len(sessions)} misi seed lama dihapus ({len(file_names)} file video)\n")


# ── Main Seed ─────────────────────────────────────────────────────────────────

def seed(reset: bool = False):
    if not check_db_connection():
        print("❌ Tidak bisa konek ke database! Periksa DATABASE_URL di .env")
        sys.exit(1)

    init_db()
    db = next(get_db())

    if reset:
        reset_seed_sessions(db)

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

    for loc, days_ago, dur_h, dur_m, kosong in SESSION_CONFIGS:
        duration_secs = dur_h * 3600 + dur_m * 60
        # 00:00–02:30 UTC = 07:00–09:30 WIB
        start = (now - timedelta(days=days_ago)).replace(
            hour=random.choice([0, 1, 2]), minute=random.choice([0, 30]), second=0, microsecond=0)
        # misi harus sudah selesai sebelum seed dijalankan
        start = min(start, now - timedelta(seconds=duration_secs + 600)).replace(second=0, microsecond=0)
        end = start + timedelta(seconds=duration_secs) if duration_secs > 0 else None
        status = SessionStatus.COMPLETED if end else SessionStatus.RUNNING

        session = MonitoringSession(
            id=generate_cuid(),
            user_id=user.id if loc in USER_LOCATIONS else admin.id,
            location_name=loc,
            start_time=start,
            end_time=end,
            status=status,
            created_at=start,
            updated_at=end or now,
        )
        db.add(session)
        db.flush()

        print(f"   ✅ Session: {loc} ({start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%H:%M') if end else 'running'}, {dur_h}j {dur_m}m){' [kosong]' if kosong else ''}")

        if kosong:
            continue

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

        # ── Detections (per frame, 1–4 ikan per spesies) ─────────────────────
        species_in_session = random.sample(SPECIES, random.randint(2, len(SPECIES)))
        frames = random.sample(range(100, 2000), random.randint(4, 8))

        for frame_no in frames:
            t = make_timestamp(start, random.randint(1, max(1, duration_secs // 60)))
            tel_id = random.choice(tel_ids) if tel_ids else None
            depth = rnd(1.5, 5.0)
            for sp in random.sample(species_in_session, random.randint(1, len(species_in_session))):
                for _ in range(random.randint(1, 4)):
                    db.add(Detection(
                        id=generate_cuid(),
                        session_id=session.id,
                        telemetry_id=tel_id,
                        species_name=sp,
                        confidence=rnd(0.62, 0.97),
                        depth_at_detection=depth,
                        frame_number=frame_no,
                        detected_at=t,
                        is_synced=False,
                        created_at=t,
                    ))
        db.flush()

        # ── Fish Counts (dihitung dari detections, sama seperti saat stream) ─
        recompute_fish_counts(db, session.id)

        # ── Video Path (klip dummy) ──────────────────────────────────────────
        file_name = f"recording_seed_{loc.replace(' ', '_').lower()}_{start.strftime('%Y%m%d_%H%M%S')}.webm"
        file_path = os.path.join(RECORDINGS_DIR, file_name)
        make_dummy_video(file_path, loc)
        vp = VideoPath(
            id=generate_cuid(),
            session_id=session.id,
            file_name=file_name,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            format='webm',
            duration=10.0,
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
    seed(reset='--reset' in sys.argv[1:])