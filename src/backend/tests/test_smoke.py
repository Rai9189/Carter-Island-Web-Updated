"""Smoke test: satu tes per perbaikan penting (Fase 4-9 + audit 2026-09-26/27)."""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

from config import RECORDINGS_DIR
from database.models import (
    MonitoringSession, SessionStatus, Telemetry, AUVStatus, Detection, FishCount, VideoPath,
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_session(db, admin, status=SessionStatus.COMPLETED, minutes_ago=0):
    t = utcnow() - timedelta(minutes=minutes_ago)
    s = MonitoringSession(user_id=admin.id, location_name="Tes", status=status,
                          start_time=t, created_at=t, updated_at=t)
    db.add(s)
    db.commit()
    return s


@pytest.fixture(scope="module")
def mission(admin):
    """Satu misi selesai berisi sedikit data di setiap tabel."""
    from database.connection import SessionLocal
    db = SessionLocal()
    s = make_session(db, admin)
    now = utcnow()
    db.add_all([
        Telemetry(session_id=s.id, timestamp=now, depth=2, ph_level=7.1, tds_value=300,
                  dissolved_oxygen=6.5, water_temp=28),
        AUVStatus(session_id=s.id, timestamp=now, heading="90"),
        Detection(session_id=s.id, species_name="ikan", confidence=0.9, detected_at=now, frame_number=1),
        FishCount(session_id=s.id, species_name="ikan", total_ikan=1),
    ])
    db.commit()
    sid = s.id
    db.close()
    return sid


# ── Auth ─────────────────────────────────────────────────────────────

def test_public_and_protected(client):
    assert client.get("/api/health").status_code == 200
    for path in ("/api/sessions", "/api/telemetry", "/api/detections", "/api/users",
                 "/api/performance", "/api/model-info"):
        assert client.get(path).status_code == 401, path


def test_login_and_me_same_shape(client):
    r = client.post("/api/auth/login", json={"email": "admin@tes.com", "password": "rahasia88"})
    client.cookies.clear()  # cookie login admin jangan terbawa ke tes "tanpa token"
    assert r.status_code == 200
    login_user = r.json()["user"]
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + r.json()["access_token"]})
    assert me.status_code == 200 and me.json()["user"] == login_user
    assert login_user["createdAt"].endswith("Z")


def test_login_rate_limit(client):
    bad = {"email": "nobody@tes.com", "password": "salah-salah"}
    codes = [client.post("/api/auth/login", json=bad).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_register_admin_only(client, user_h):
    body = {"fullName": "X", "email": "x@tes.com", "phoneNumber": "08123456789",
            "password": "rahasia88", "role": "ADMIN"}
    assert client.post("/api/auth/register", json=body).status_code == 401
    assert client.post("/api/auth/register", json=body, headers=user_h).status_code == 403


# ── Validasi & pagination ────────────────────────────────────────────

def test_malformed_body_is_400(client, admin_h):
    r = client.post("/api/users", headers=admin_h,
                    json={"fullName": 123, "email": "y@tes.com", "phoneNumber": "08123456789",
                          "password": "rahasia88", "role": "USER"})
    assert r.status_code == 400
    r = client.post("/api/users", headers=admin_h,
                    json={"fullName": "Y", "email": "y@tes.com", "phoneNumber": "08123456789",
                          "password": "pendek", "role": "USER"})
    assert r.status_code == 400


@pytest.mark.parametrize("path", ["/api/detections", "/api/telemetry"])
@pytest.mark.parametrize("query", ["limit=0", "limit=-5", "page=-1", "offset=-1", "limit=999999999"])
def test_pagination_clamped(client, user_h, mission, path, query):
    assert client.get(f"{path}?{query}", headers=user_h).status_code == 200


def test_phone_validation(client, admin_h):
    from core.validation import check_phone
    for ok in ["08123456789", "+62-812-3456-7890", "62 812 3456 789", "0812.3456.7890"]:
        assert check_phone(ok) == ok
    for bad in ["abc123", "0812", "021-555-1234", "+1 555 123 4567", "08123456789012", "081234567"]:
        with pytest.raises(ValueError):
            check_phone(bad)
    body = {"fullName": "Z", "email": "z@tes.com", "phoneNumber": "08abc",
            "password": "rahasia88", "role": "USER"}
    assert client.post("/api/users", headers=admin_h, json=body).status_code == 400
    assert client.post("/api/auth/register", headers=admin_h, json=body).status_code == 422


def test_last_admin_cannot_demote_self(client, admin_h, admin):
    body = {"fullName": "admin", "email": "admin@tes.com", "phoneNumber": "08123456789", "role": "USER"}
    assert client.put(f"/api/users/{admin.id}", headers=admin_h, json=body).status_code == 400


# ── Waktu (UTC + 'Z') ────────────────────────────────────────────────

def test_timestamps_have_zone(client, user_h, mission):
    s = client.get(f"/api/sessions/{mission}", headers=user_h).json()["data"]
    assert s["startTime"].endswith("Z")
    t = client.get(f"/api/telemetry?session_id={mission}", headers=user_h).json()["data"][0]
    assert t["timestamp"].endswith("Z")


# ── Rekaman (audit no.6) ─────────────────────────────────────────────

def _recording(db, session_id, name):
    path = os.path.join(RECORDINGS_DIR, name)
    open(path, "wb").write(b"x")
    v = VideoPath(session_id=session_id, file_name=name, file_path=path, format="webm")
    db.add(v)
    db.commit()
    return v.id, path


def test_delete_recording_removes_file(client, db, admin, admin_h, user_h):
    s = make_session(db, admin)
    vid, path = _recording(db, s.id, "recording_pytest_a.webm")
    assert client.delete(f"/api/recordings/{vid}", headers=user_h).status_code == 403
    assert os.path.exists(path)
    assert client.delete(f"/api/recordings/{vid}", headers=admin_h).status_code == 200
    assert not os.path.exists(path)


def test_recordings_list_has_mission_name(client, db, admin, admin_h):
    s = make_session(db, admin)
    vid, _ = _recording(db, s.id, "recording_pytest_m.webm")
    rows = client.get("/api/recordings", params={"session_id": s.id}, headers=admin_h).json()["data"]
    assert [r["missionName"] for r in rows if r["id"] == vid] == ["Tes"]


def test_delete_session_removes_files(client, db, admin, admin_h):
    s = make_session(db, admin)
    _, p1 = _recording(db, s.id, "recording_pytest_s1.webm")
    _, p2 = _recording(db, s.id, "recording_pytest_s2.webm")
    assert client.delete(f"/api/sessions/{s.id}", headers=admin_h).status_code == 200
    assert not os.path.exists(p1) and not os.path.exists(p2)


# ── Misi tertinggal (audit no.3) ─────────────────────────────────────

def test_stale_running_session_aborted(db, admin, monkeypatch):
    import core.scheduler as sch
    from webrtc import peer_connection as pc

    monkeypatch.setattr(sch, "STALE_SESSION_MINUTES", 10)
    monkeypatch.setattr(sch, "_last_stream_at", None)
    s = make_session(db, admin, SessionStatus.RUNNING, minutes_ago=11)

    monkeypatch.setitem(pc.peer_connections, "pytest", object())
    asyncio.run(sch.stale_session_job())
    db.refresh(s)
    assert s.status == SessionStatus.RUNNING, "stream tersambung → jangan ditutup"

    monkeypatch.delitem(pc.peer_connections, "pytest")
    monkeypatch.setattr(sch, "_last_stream_at", utcnow() - timedelta(minutes=11))
    asyncio.run(sch.stale_session_job())
    db.commit()  # akhiri snapshot transaksi lama (MySQL REPEATABLE READ)
    db.refresh(s)
    assert s.status == SessionStatus.ABORTED and s.end_time is not None


# ── Sapuan: tidak ada 5xx ────────────────────────────────────────────

GET_ENDPOINTS = [
    "/api/sessions", "/api/sessions/active", "/api/sessions/{sid}",
    "/api/telemetry", "/api/telemetry/latest?session_id={sid}", "/api/telemetry/export",
    "/api/auv-status", "/api/auv-status/latest?session_id={sid}",
    "/api/detections", "/api/detections/stats", "/api/detections/stats/by-session",
    "/api/detections/export",
    "/api/fish-counts", "/api/fish-counts/summary", "/api/fish-counts/session/{sid}",
    "/api/fish-counts/export",
    "/api/recordings", "/api/users",
    "/api/analytics/detections", "/api/analytics/telemetry", "/api/analytics/auv-status",
    "/api/analytics/sessions", "/api/analytics/sessions/by-date", "/api/analytics/sessions/{sid}",
    "/api/performance", "/api/model-info", "/api/auth/me",
]


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_no_server_error(client, admin_h, mission, path):
    r = client.get(path.format(sid=mission), headers=admin_h)
    assert r.status_code < 500, f"{path} -> {r.status_code} {r.text[:200]}"
