"""
Helper untuk endpoint export CSV.

Dipakai oleh routers/telemetry.py, routers/detections.py, routers/fish_counts.py
untuk menghindari duplikasi logic StreamingResponse + parsing tanggal.
"""
import csv
import io
from typing import Optional
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from core.timeutil import parse_local


# ==========================
# csv_response — build StreamingResponse dari header + rows
# ==========================
def csv_response(filename: str, header: list, rows: list) -> StreamingResponse:
    """
    Build CSV response yang rapi dibuka di Excel/Google Sheets.

    UTF-8 BOM (\\ufeff) di-prepend supaya Excel mendeteksi encoding UTF-8
    dengan benar (tanpa BOM, Excel sering salah-baca sebagai ANSI/Latin-1).
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)

    csv_bytes = ("﻿" + buffer.getvalue()).encode("utf-8")

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==========================
# parse_date_range — validasi & parse query param from/to
# ==========================
def parse_date_range(from_str: Optional[str], to_str: Optional[str]) -> tuple:
    """
    Parse tanggal ISO 8601 dari query param `from`/`to`.

    Raises:
        HTTPException 400 kalau format tanggal tidak valid atau
        from > to (rentang terbalik → hasil kosong diam-diam).
    """
    from_date = to_date = None
    try:
        if from_str:
            from_date = parse_local(from_str)
        if to_str:
            to_date = parse_local(to_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Format tanggal tidak valid. Gunakan ISO 8601 (YYYY-MM-DD)",
        )

    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="Tanggal awal tidak boleh setelah tanggal akhir",
        )

    return from_date, to_date
