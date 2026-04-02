"""
Script verifikasi Fase 4 — Migrasi Semua API Route.

Cara pakai (dari folder src/backend/, venv aktif):
    python verify_fase4.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check(label, fn):
    try:
        result = fn()
        print(f"  [OK] {label}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


def main():
    print("=" * 55)
    print("VERIFIKASI FASE 4 — Migrasi Semua API Route")
    print("=" * 55)

    all_ok = True

    # -----------------------------------------------
    print("\n1. Import semua router baru")
    # -----------------------------------------------
    for name in ["users", "telemetry", "auv_status", "detections",
                 "recordings", "analytics"]:
        ok = check(f"Import routers.{name}",
                   lambda n=name: __import__(f"routers.{n}"))
        all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n2. Cek semua router terdaftar di main.py")
    # -----------------------------------------------
    def check_main_routers():
        with open("main.py", "r") as f:
            content = f.read()
        required = [
            "users_router", "telemetry_router", "auv_status_router",
            "detections_router", "recordings_router", "analytics_router"
        ]
        missing = [r for r in required if r not in content]
        if missing:
            raise Exception(f"Router belum terdaftar: {missing}")
        return f"{len(required)} router terdaftar"

    ok = check("Semua router ada di main.py", check_main_routers)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n3. Test endpoint via server (server harus jalan)")
    # -----------------------------------------------
    import httpx

    BASE = "http://localhost:8000"

    def get_token():
        from database.connection import SessionLocal
        from database.models import User
        from auth.jwt import create_access_token
        with SessionLocal() as db:
            user = db.query(User).first()
            if not user:
                raise Exception("Tidak ada user di DB")
            return create_access_token(user.id, user.email, user.role.value)

    def check_server():
        try:
            r = httpx.get(f"{BASE}/api/health", timeout=3.0)
            return f"Server jalan (status {r.status_code})"
        except httpx.ConnectError:
            raise Exception("Server belum jalan — jalankan python main.py dulu")

    ok = check("Server jalan di port 8000", check_server)
    if not ok:
        print("\n  Server belum jalan, skip test endpoint.")
        print("  Jalankan: python main.py, lalu test manual di http://localhost:8000/docs")
        all_ok = False
    else:
        try:
            token = get_token()
            headers = {"Authorization": f"Bearer {token}"}

            endpoints = [
                ("GET", "/api/users", None),
                ("GET", "/api/telemetry/latest", None),
                ("GET", "/api/auv-status/latest", None),
                ("GET", "/api/detections", None),
                ("GET", "/api/detections/stats", None),
                ("GET", "/api/recordings", None),
                ("GET", "/api/analytics/detections", None),
                ("GET", "/api/analytics/telemetry", None),
                ("GET", "/api/analytics/auv-status", None),
            ]

            for method, path, body in endpoints:
                def test_endpoint(m=method, p=path, b=body, h=headers):
                    r = httpx.request(m, f"{BASE}{p}", headers=h,
                                     json=b, timeout=5.0)
                    if r.status_code in (200, 201, 404):
                        return f"HTTP {r.status_code}"
                    raise Exception(f"HTTP {r.status_code}: {r.text[:80]}")

                ok = check(f"{method} {path}", test_endpoint)
                all_ok = all_ok and ok

        except Exception as e:
            print(f"  [FAIL] Tidak bisa generate token: {e}")
            all_ok = False

    # -----------------------------------------------
    print("\n" + "=" * 55)
    if all_ok:
        print("HASIL: SEMUA CHECK PASSED — Fase 4 selesai!")
        print("Siap lanjut ke Fase 5 (Background Tasks)")
    else:
        print("HASIL: ADA CHECK YANG GAGAL — periksa error di atas")
    print("=" * 55)
    print()
    print("Cek semua endpoint di Swagger UI:")
    print("  http://localhost:8000/docs")


if __name__ == "__main__":
    main()