"""
Helper validasi input numerik dari request body mentah (dict).

Dipakai endpoint yang terima payload dict tanpa Pydantic schema
(telemetry, auv-status, fish-counts, sync) supaya field non-numeric
tidak bikin ValueError mentah bocor jadi 500.
"""
from typing import Any, Optional


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
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} harus berupa angka, dapat: {value!r}")


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
