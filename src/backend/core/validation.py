"""
Helper validasi input dari request body mentah (dict).

Dipakai endpoint yang terima payload dict tanpa Pydantic schema
(users, sessions, recordings, telemetry, auv-status, fish-counts, sync)
supaya field bertipe salah tidak bikin error mentah bocor jadi 500.
Semua helper raise ValueError polos; caller yang mengubahnya jadi 400.
"""
import math
from typing import Any, Optional

# Berlaku saat password dibuat/diganti (register, admin create/update user).
PASSWORD_MIN_LENGTH = 8


def safe_str(value: Any, field_name: str) -> str:
    """Parse value ke string ter-strip. None -> "" (caller cek wajib/tidak)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} harus berupa teks")
    return value.strip()


def check_password(password: str) -> str:
    """Raise ValueError kalau password lebih pendek dari PASSWORD_MIN_LENGTH."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password minimal {PASSWORD_MIN_LENGTH} karakter")
    return password


def safe_float(value: Any, field_name: str, default: Optional[float] = None) -> float:
    """
    Parse value ke float.

    - value None dan default diisi -> return default (field opsional).
    - value None dan default None -> raise ValueError (field wajib).
    - value ada tapi tidak bisa di-parse -> raise ValueError.
    """
    if value is None:
        if default is None:
            raise ValueError(f"{field_name} wajib diisi")
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} harus berupa angka, dapat: {value!r}")
    # NaN/Infinity lolos float() tapi ditolak MySQL saat insert
    if not math.isfinite(result):
        raise ValueError(f"{field_name} harus berupa angka, dapat: {value!r}")
    return result


def safe_int(value: Any, field_name: str, default: Optional[int] = None) -> int:
    """Sama seperti safe_float, tapi untuk int."""
    if value is None:
        if default is None:
            raise ValueError(f"{field_name} wajib diisi")
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} harus berupa angka bulat, dapat: {value!r}")
