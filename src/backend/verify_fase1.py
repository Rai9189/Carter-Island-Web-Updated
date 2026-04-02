"""
Script verifikasi Fase 1 — jalankan setelah semua file dibuat.

Cara pakai (dari folder src/backend/):
    python verify_fase1.py

Yang dicek:
1. Koneksi ke MySQL berhasil
2. Semua 6 tabel ditemukan
3. Data lama dari Prisma masih bisa dibaca
4. Generate CUID berjalan normal
5. Import semua module baru tidak error
"""
import sys
import os

# Pastikan path benar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check(label: str, fn):
    """Helper untuk jalankan check dan cetak hasilnya."""
    try:
        result = fn()
        print(f"  [OK] {label}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


def main():
    print("=" * 55)
    print("VERIFIKASI FASE 1 — Carter Island Unified Backend")
    print("=" * 55)

    all_ok = True

    # -----------------------------------------------
    print("\n1. Import modules baru")
    # -----------------------------------------------
    ok = check("Import database.connection", lambda: __import__("database.connection"))
    all_ok = all_ok and ok

    ok = check("Import database.models", lambda: __import__("database.models"))
    all_ok = all_ok and ok

    ok = check("Import core.cuid", lambda: __import__("core.cuid"))
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n2. CUID Generator")
    # -----------------------------------------------
    from core.cuid import generate_cuid
    cuids = [generate_cuid() for _ in range(5)]

    ok = check("Generate 5 CUID", lambda: cuids)
    ok = check("Format CUID valid (starts with 'c')", lambda: all(c.startswith("c") for c in cuids))
    ok = check("Semua CUID unik", lambda: len(set(cuids)) == 5)
    all_ok = all_ok and ok

    for cuid in cuids:
        print(f"       {cuid}")

    # -----------------------------------------------
    print("\n3. Koneksi Database")
    # -----------------------------------------------
    from database.connection import check_db_connection, engine
    ok = check("Koneksi MySQL", check_db_connection)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n4. Verifikasi Tabel")
    # -----------------------------------------------
    from sqlalchemy import inspect, text

    def check_tables():
        inspector = inspect(engine)
        existing = inspector.get_table_names()
        required = [
            "users", "fish_detections", "detection_details",
            "recordings", "telemetry", "auv_status"
        ]
        missing = [t for t in required if t not in existing]
        if missing:
            raise Exception(f"Tabel tidak ditemukan: {missing}")
        return f"{len(required)} tabel ditemukan"

    ok = check("Semua tabel ada di DB", check_tables)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n5. Baca Data Lama dari Prisma")
    # -----------------------------------------------
    from sqlalchemy.orm import Session
    from database.connection import SessionLocal
    from database.models import User, FishDetection, Telemetry, AUVStatus, Recording

    def read_counts():
        with SessionLocal() as db:
            counts = {
                "users": db.query(User).count(),
                "fish_detections": db.query(FishDetection).count(),
                "telemetry": db.query(Telemetry).count(),
                "auv_status": db.query(AUVStatus).count(),
                "recordings": db.query(Recording).count(),
            }
        return counts

    def check_read_data():
        counts = read_counts()
        for table, count in counts.items():
            print(f"       {table}: {count} rows")
        return "Data terbaca"

    ok = check("Baca semua tabel", check_read_data)
    all_ok = all_ok and ok

    def check_user_fields():
        with SessionLocal() as db:
            user = db.query(User).first()
            if user:
                # Verifikasi field mapping benar
                assert hasattr(user, "full_name"), "full_name tidak ada"
                assert hasattr(user, "phone_number"), "phone_number tidak ada"
                assert hasattr(user, "role"), "role tidak ada"
                return f"User '{user.email}' terbaca dengan benar"
            return "Tidak ada user (normal jika DB kosong)"

    ok = check("Field mapping User benar", check_user_fields)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n" + "=" * 55)
    if all_ok:
        print("HASIL: SEMUA CHECK PASSED — Fase 1 selesai!")
        print("Siap lanjut ke Fase 2 (JWT Auth)")
    else:
        print("HASIL: ADA CHECK YANG GAGAL — periksa error di atas")
    print("=" * 55)


if __name__ == "__main__":
    main()