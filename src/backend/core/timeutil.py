"""
Helper zona waktu.

Aturan proyek:
- Kolom DATETIME menyimpan UTC tanpa zona (koneksi DB di-set ke +00:00,
  lihat database/connection.py).
- API mengirim waktu sebagai ISO 8601 UTC berakhiran 'Z' (iso_utc) supaya
  browser menampilkannya di zona lokal user dengan benar.
- Filter tanggal/jam tanpa zona dari frontend = waktu lokal APP_TIMEZONE
  (parse_local) → dikonversi ke UTC untuk query.
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from config import APP_TIMEZONE

LOCAL_TZ = ZoneInfo(APP_TIMEZONE)


def iso_utc(dt: Optional[datetime]) -> Optional[str]:
    """datetime dari DB (UTC naive) atau aware → '2026-09-26T15:13:53Z'."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_local(value: str) -> datetime:
    """
    Teks ISO dari filter frontend → datetime UTC naive untuk dibandingkan
    dengan kolom DB. Tanpa zona = waktu lokal APP_TIMEZONE; dengan zona
    ('Z' / '+07:00') dipakai apa adanya. Raise ValueError kalau format salah.
    """
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def local_str(dt: Optional[datetime]) -> str:
    """datetime DB (UTC naive) → 'YYYY-MM-DD HH:MM:SS' di APP_TIMEZONE (untuk CSV)."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
