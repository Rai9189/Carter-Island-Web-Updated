"""
Smoke test backend — jalankan dari src/backend:

    venv\\Scripts\\python -m pytest tests -q

DB asli TIDAK disentuh: DB `carter_island_test` (server MySQL yang sama dengan
DATABASE_URL di .env) dibuat ulang tiap run lewat migrasi Alembic, rekaman
diarahkan ke folder sementara. App dipakai lewat TestClient tanpa lifespan →
YOLO, scheduler, dan RTSP tidak jalan (tidak butuh ROV).
"""
import os
import re
import sys
import tempfile

import pymysql
import pytest
from dotenv import load_dotenv

TEST_DB = "carter_island_test"

# Harus terjadi SEBELUM modul backend di-import (config.py membaca env saat import)
load_dotenv()
_base = os.environ["DATABASE_URL"].rsplit("/", 1)[0]
_m = re.match(r"mysql(?:\+pymysql)?://([^:@]+):?([^@]*)@([^:/]+):?(\d*)", _base)
_conn = pymysql.connect(user=_m[1], password=_m[2], host=_m[3], port=int(_m[4] or 3306))
with _conn.cursor() as _c:
    _c.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    _c.execute(f"CREATE DATABASE {TEST_DB}")
_conn.close()
os.environ["DATABASE_URL"] = f"{_base}/{TEST_DB}"
os.environ["RECORDINGS_DIR"] = tempfile.mkdtemp(prefix="carter_rec_")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from database.connection import init_db, SessionLocal  # noqa: E402
from database.models import User, Role  # noqa: E402
from auth.password import hash_password  # noqa: E402
from auth.jwt import create_access_token  # noqa: E402

init_db()
PASSWORD = "rahasia88"


def _add_user(email: str, role: Role) -> User:
    db = SessionLocal()
    u = User(username=email.split("@")[0], email=email, password=hash_password(PASSWORD),
             phone_number="0812", role=role)
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return u


ADMIN = _add_user("admin@tes.com", Role.ADMIN)
USER = _add_user("user@tes.com", Role.USER)


def _auth(u: User) -> dict:
    return {"Authorization": "Bearer " + create_access_token(u.id, u.email, u.role.value, u.username)}


@pytest.fixture(scope="session")
def client():
    import main
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="session")
def admin():
    return ADMIN


@pytest.fixture(scope="session")
def admin_h():
    return _auth(ADMIN)


@pytest.fixture(scope="session")
def user_h():
    return _auth(USER)
