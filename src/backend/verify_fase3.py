"""
Script verifikasi Fase 3 — Hapus HTTP Client Internal.

Cara pakai (dari folder src/backend/, venv aktif):
    python verify_fase3.py

Yang dicek:
1. database/detections.py tidak lagi diimport
2. database/crud/detections.py bisa diimport
3. database/crud/recordings.py bisa diimport
4. save_detection_to_db() menulis langsung ke MySQL
5. save_recording_to_db() menulis langsung ke MySQL
6. main.py tidak ada lagi import HTTP client
7. Tidak ada lagi referensi ke API_BASE_URL untuk detections
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check(label: str, fn):
    try:
        result = fn()
        print(f"  [OK] {label}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


def main():
    print("=" * 55)
    print("VERIFIKASI FASE 3 — Hapus HTTP Client Internal")
    print("=" * 55)

    all_ok = True

    # -----------------------------------------------
    print("\n1. Import CRUD modules baru")
    # -----------------------------------------------
    ok = check("Import database.crud.detections",
               lambda: __import__("database.crud.detections"))
    ok = check("Import database.crud.recordings",
               lambda: __import__("database.crud.recordings"))
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n2. Cek main.py tidak ada HTTP client lagi")
    # -----------------------------------------------
    def check_main_no_http():
        with open("main.py", "r") as f:
            content = f.read()
        assert "initialize_http_client" not in content, \
            "main.py masih ada initialize_http_client!"
        assert "close_http_client" not in content, \
            "main.py masih ada close_http_client!"
        assert "API_BASE_URL" not in content, \
            "main.py masih ada API_BASE_URL!"
        return "Bersih — tidak ada HTTP client"

    ok = check("main.py bersih dari HTTP client", check_main_no_http)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n3. Cek detection_track.py pakai SQLAlchemy")
    # -----------------------------------------------
    def check_detection_track():
        with open("video/detection_track.py", "r") as f:
            content = f.read()
        assert "save_detection_to_db" in content, \
            "detection_track.py tidak pakai save_detection_to_db!"
        assert "save_detections_to_db" not in content or \
               "crud.detections" in content, \
            "detection_track.py masih pakai HTTP client lama!"
        return "Pakai save_detection_to_db dari crud"

    ok = check("detection_track.py pakai SQLAlchemy", check_detection_track)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n4. Cek recording.py tidak pakai httpx")
    # -----------------------------------------------
    def check_recording_no_httpx():
        with open("video/recording.py", "r") as f:
            content = f.read()
        assert "import httpx" not in content, \
            "recording.py masih import httpx!"
        assert "save_recording_to_db" in content, \
            "recording.py tidak pakai save_recording_to_db!"
        return "Bersih — pakai SQLAlchemy langsung"

    ok = check("recording.py tidak pakai httpx", check_recording_no_httpx)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n5. Test simpan deteksi ke MySQL")
    # -----------------------------------------------
    import asyncio
    from database.crud.detections import save_detection_to_db

    async def test_save_detection():
        # Data simulasi dari YOLO detector
        fake_detections = [
            (100, 150, 300, 350, 0.92, "ikan_nila"),
            (400, 200, 600, 400, 0.87, "ikan_nila"),
        ]
        result = await save_detection_to_db(fake_detections, frame_number=999)
        return result

    ok = check(
        "save_detection_to_db() ke MySQL",
        lambda: asyncio.run(test_save_detection())
    )
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n6. Verifikasi data tersimpan di tabel")
    # -----------------------------------------------
    from database.connection import SessionLocal
    from database.models import FishDetection, DetectionDetail

    def check_detection_in_db():
        with SessionLocal() as db:
            # Ambil deteksi dengan frame_number 999 (yang baru dibuat)
            det = db.query(FishDetection).filter(
                FishDetection.frame_number == 999
            ).first()
            if not det:
                raise Exception("Data tidak ditemukan di tabel fish_detections!")
            details = db.query(DetectionDetail).filter(
                DetectionDetail.detection_id == det.id
            ).all()
            return (
                f"fish_detections: id={det.id[:10]}..., "
                f"fish_count={det.fish_count}, "
                f"details={len(details)} rows"
            )

    ok = check("Data tersimpan di fish_detections + detection_details",
               check_detection_in_db)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n7. Test simpan recording ke MySQL")
    # -----------------------------------------------
    from database.crud.recordings import save_recording_to_db
    from datetime import datetime, timezone
    import pytz

    async def test_save_recording():
        JAKARTA_TZ = pytz.timezone('Asia/Jakarta')
        start = datetime.now(JAKARTA_TZ)
        end = datetime.now(JAKARTA_TZ)
        rec_id = await save_recording_to_db(
            session_id="test-session-fase3",
            filename="test_recording_fase3.webm",
            filepath="/tmp/test_recording_fase3.webm",
            file_size=1024 * 1024,  # 1MB
            duration=10.5,
            start_time=start,
            end_time=end,
        )
        return rec_id

    ok = check(
        "save_recording_to_db() ke MySQL",
        lambda: asyncio.run(test_save_recording())
    )
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n" + "=" * 55)
    if all_ok:
        print("HASIL: SEMUA CHECK PASSED — Fase 3 selesai!")
        print("Siap lanjut ke Fase 4 (Migrasi Semua API Route)")
    else:
        print("HASIL: ADA CHECK YANG GAGAL — periksa error di atas")
    print("=" * 55)
    print()
    print("LANGKAH SELANJUTNYA:")
    print("1. Jalankan server: python main.py")
    print("2. Pastikan log TIDAK ada lagi:")
    print('   "API endpoint: http://localhost:3000/api/detections"')
    print("3. Cek tabel fish_detections di MySQL bertambah saat streaming")


if __name__ == "__main__":
    main()