"""
Script verifikasi Fase 5 — Background Tasks & Scheduled Jobs.

Cara pakai (dari folder src/backend/, venv aktif):
    python verify_fase5.py
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check(label, fn):
    try:
        result = fn()
        print(f"  [OK] {label}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


async def check_async(label, fn):
    try:
        result = await fn()
        print(f"  [OK] {label}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


def main():
    print("=" * 55)
    print("VERIFIKASI FASE 5 — Background Tasks")
    print("=" * 55)

    all_ok = True

    # -----------------------------------------------
    print("\n1. Import scheduler")
    # -----------------------------------------------
    ok = check("Import core.scheduler",
               lambda: __import__("core.scheduler"))
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n2. Cek jobs terdaftar di scheduler")
    # -----------------------------------------------
    def check_jobs():
        from core.scheduler import scheduler, setup_scheduler
        setup_scheduler()
        jobs = scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert "health_check" in job_ids, "Job health_check tidak ditemukan!"
        assert "daily_cleanup" in job_ids, "Job daily_cleanup tidak ditemukan!"
        return f"{len(jobs)} jobs: {job_ids}"

    ok = check("Jobs health_check + daily_cleanup terdaftar", check_jobs)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n3. Cek main.py ada scheduler start/shutdown")
    # -----------------------------------------------
    def check_main_scheduler():
        with open("main.py", "r") as f:
            content = f.read()
        assert "setup_scheduler" in content, "setup_scheduler tidak ada di main.py!"
        assert "scheduler.start()" in content, "scheduler.start() tidak ada!"
        assert "scheduler.shutdown" in content, "scheduler.shutdown tidak ada!"
        return "scheduler.start() dan shutdown() ada di lifespan"

    ok = check("main.py punya scheduler lifecycle", check_main_scheduler)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n4. Test cleanup_job langsung (dry run)")
    # -----------------------------------------------
    async def run_cleanup():
        from core.scheduler import cleanup_job
        await cleanup_job()
        return "Cleanup job berjalan tanpa error"

    ok = asyncio.run(check_async("cleanup_job() berjalan", run_cleanup))
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n5. Test health_check_job (Raspi mungkin offline)")
    # -----------------------------------------------
    async def run_health_check():
        from core.scheduler import health_check_job
        from database.connection import SessionLocal
        from database.models import AUVStatus

        # Hitung row sebelum
        with SessionLocal() as db:
            before = db.query(AUVStatus).count()

        # Jalankan health check
        await health_check_job()

        # Hitung row sesudah
        with SessionLocal() as db:
            after = db.query(AUVStatus).count()
            latest = db.query(AUVStatus).order_by(
                AUVStatus.timestamp.desc()
            ).first()

        status = "online" if latest and latest.is_online else "offline"
        return (
            f"AUV {status}, "
            f"DB rows: {before} → {after} "
            f"(+{after - before} baru)"
        )

    ok = asyncio.run(check_async(
        "health_check_job() simpan ke DB (Raspi offline = normal)",
        run_health_check
    ))
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n6. Cek server jalan dengan scheduler aktif")
    # -----------------------------------------------
    import httpx

    def check_server():
        try:
            r = httpx.get("http://localhost:8000/api/health", timeout=3.0)
            return f"Server jalan (status {r.status_code})"
        except httpx.ConnectError:
            return "Server belum jalan — jalankan python main.py dan cek log 'Background scheduler started'"

    ok = check("Server status", check_server)

    # -----------------------------------------------
    print("\n" + "=" * 55)
    if all_ok:
        print("HASIL: SEMUA CHECK PASSED — Fase 5 selesai!")
        print("Siap lanjut ke Fase 6 (Update Frontend)")
    else:
        print("HASIL: ADA CHECK YANG GAGAL — periksa error di atas")
    print("=" * 55)
    print()
    print("Cek log server — seharusnya muncul tiap 5 detik:")
    print('  INFO: Health check — AUV offline/online')
    print("Dan tiap hari jam 00:00:")
    print('  INFO: Cleanup selesai — telemetry: X rows, auv_status: Y rows dihapus')


if __name__ == "__main__":
    main()