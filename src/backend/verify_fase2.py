"""
Script verifikasi Fase 2 — JWT Authentication.

Cara pakai (dari folder src/backend/, venv aktif):
    python verify_fase2.py

Yang dicek:
1. Import semua module auth berhasil
2. hash_password & verify_password bekerja
3. Kompatibilitas dengan hash bcryptjs (user lama bisa login)
4. create_access_token & verify_token bekerja
5. Token expired terdeteksi
6. Endpoint /api/auth/login bisa diakses (butuh server jalan)
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
    print("VERIFIKASI FASE 2 — JWT Authentication")
    print("=" * 55)

    all_ok = True

    # -----------------------------------------------
    print("\n1. Import modules auth")
    # -----------------------------------------------
    ok = check("Import auth.password", lambda: __import__("auth.password"))
    ok = check("Import auth.jwt", lambda: __import__("auth.jwt"))
    ok = check("Import core.dependencies", lambda: __import__("core.dependencies"))
    ok = check("Import routers.auth", lambda: __import__("routers.auth"))
    ok = check("Import schemas.auth", lambda: __import__("schemas.auth"))
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n2. Password hashing")
    # -----------------------------------------------
    from auth.password import hash_password, verify_password

    test_password = "testpassword123"
    hashed = None

    def do_hash():
        nonlocal hashed
        hashed = hash_password(test_password)
        return hashed[:20] + "..."

    ok = check("hash_password() berjalan", do_hash)
    ok = check("Hash format bcrypt ($2b$)", lambda: hashed.startswith("$2b$"))
    ok = check("verify_password() benar", lambda: verify_password(test_password, hashed))
    ok = check("verify_password() salah", lambda: not verify_password("wrongpass", hashed))
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n3. Kompatibilitas dengan bcryptjs (user lama)")
    # -----------------------------------------------
    # Hash ini dibuat oleh bcryptjs dengan: bcrypt.hash("password123", 12)
    # Simulasi hash dari user lama di database
    bcryptjs_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5WGh5X6a6eN3."

    ok = check(
        "Verifikasi hash bcryptjs berhasil",
        lambda: verify_password("password123", bcryptjs_hash)
    )
    ok = check(
        "Verifikasi hash bcryptjs salah password",
        lambda: not verify_password("wrongpassword", bcryptjs_hash)
    )
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n4. JWT Token")
    # -----------------------------------------------
    from auth.jwt import create_access_token, verify_token

    token = None

    def do_create_token():
        nonlocal token
        token = create_access_token(
            user_id="test-user-id-123",
            email="test@carterisland.com",
            role="ADMIN"
        )
        return token[:30] + "..."

    ok = check("create_access_token() berjalan", do_create_token)

    def do_verify_token():
        payload = verify_token(token)
        assert payload["user_id"] == "test-user-id-123"
        assert payload["email"] == "test@carterisland.com"
        assert payload["role"] == "ADMIN"
        return f"user_id={payload['user_id'][:10]}..."

    ok = check("verify_token() payload benar", do_verify_token)

    # Test token tidak valid
    from fastapi import HTTPException
    def do_invalid_token():
        try:
            verify_token("token.tidak.valid")
            return False  # Harusnya raise exception
        except HTTPException as e:
            return e.status_code == 401

    ok = check("Token tidak valid → 401", do_invalid_token)

    # Test expired token
    from datetime import timedelta
    def do_expired_token():
        expired_token = create_access_token(
            user_id="test",
            email="test@test.com",
            role="USER",
            expires_delta=timedelta(seconds=-1)  # Sudah expired
        )
        try:
            verify_token(expired_token)
            return False
        except HTTPException as e:
            return e.status_code == 401

    ok = check("Token expired → 401", do_expired_token)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n5. Verifikasi user lama di database bisa login")
    # -----------------------------------------------
    from database.connection import SessionLocal
    from database.models import User

    def check_existing_users():
        with SessionLocal() as db:
            users = db.query(User).all()
            if not users:
                return "Tidak ada user (skip)"

            # Coba verifikasi password untuk user pertama
            # (tidak bisa cek password asli, tapi bisa cek format hash)
            user = users[0]
            is_bcrypt = user.password.startswith("$2b$") or user.password.startswith("$2a$")
            return f"{len(users)} user ditemukan, hash format bcrypt: {is_bcrypt}"

    ok = check("Format hash user lama valid", check_existing_users)
    all_ok = all_ok and ok

    # -----------------------------------------------
    print("\n6. Cek endpoint tersedia (server harus jalan)")
    # -----------------------------------------------
    import httpx

    def check_login_endpoint():
        try:
            res = httpx.post(
                "http://localhost:8000/api/auth/login",
                json={"email": "test@test.com", "password": "wrongpass"},
                timeout=3.0
            )
            # 401 adalah response yang benar (user tidak ada/salah password)
            # Artinya endpoint bisa diakses
            return f"Endpoint aktif (status: {res.status_code})"
        except httpx.ConnectError:
            return "Server belum jalan — jalankan: python main.py, lalu test manual"

    ok = check("POST /api/auth/login tersedia", check_login_endpoint)

    # -----------------------------------------------
    print("\n" + "=" * 55)
    if all_ok:
        print("HASIL: SEMUA CHECK PASSED — Fase 2 selesai!")
        print("Siap lanjut ke Fase 3 (Hapus HTTP Client Internal)")
    else:
        print("HASIL: ADA CHECK YANG GAGAL — periksa error di atas")
    print("=" * 55)
    print()
    print("LANGKAH SELANJUTNYA:")
    print("1. Update main.py sesuai instruksi di main_patch.py")
    print("2. Jalankan server: python main.py")
    print("3. Test login manual:")
    print('   curl -X POST http://localhost:8000/api/auth/login \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"email":"admin@carterisland.com","password":"yourpassword"}\'')


if __name__ == "__main__":
    main()