"""
Router fish_counts — agregasi jumlah populasi ikan per spesies per sesi.

Tabel fish_counts menyimpan hasil agregasi deteksi YOLO:
  - Berapa total individu per spesies dalam satu sesi misi
  - Diupdate secara berkala selama sesi berlangsung
  - Digunakan halaman Analytics untuk chart populasi ikan

Endpoints:
  POST  /api/fish-counts              — simpan/update agregasi (dari YOLO)
  GET   /api/fish-counts              — list dengan filter session
  GET   /api/fish-counts/session/{id} — semua spesies dalam satu sesi
  GET   /api/fish-counts/summary      — ringkasan total semua sesi
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.connection import get_db
from database.models import FishCount, MonitoringSession
from core.dependencies import get_current_user
from core.cuid import generate_cuid

logger = logging.getLogger("carter-backend")

router = APIRouter(prefix="/api/fish-counts", tags=["Fish Counts"])


# ==========================
# POST /api/fish-counts — simpan atau update agregasi
# Dipanggil oleh YOLO setelah selesai deteksi per frame
# ==========================
@router.post("", status_code=status.HTTP_201_CREATED)
def save_fish_count(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Simpan atau update jumlah ikan per spesies dalam satu sesi.
    Jika spesies sudah ada dalam sesi, total_count akan di-update
    (ditambah dengan count baru). Jika belum ada, buat record baru.

    Payload:
        session_id   : str — wajib
        species_name : str — nama spesies
        count        : int — jumlah individu yang terdeteksi
    """
    session_id   = body.get("session_id") or body.get("sessionId")
    species_name = body.get("species_name") or body.get("speciesName")
    count        = body.get("count", 0)

    if not session_id or not species_name:
        raise HTTPException(
            status_code=400,
            detail="session_id dan species_name wajib diisi"
        )

    # Verifikasi sesi ada
    session = db.query(MonitoringSession).filter(
        MonitoringSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    now = datetime.now(timezone.utc)

    # Cek apakah spesies sudah ada dalam sesi ini
    existing = db.query(FishCount).filter(
        FishCount.session_id == session_id,
        FishCount.species_name == species_name,
    ).first()

    if existing:
        # Update total count — tambah dengan deteksi baru
        existing.total_count += int(count)
        existing.updated_at   = now
        db.commit()
        db.refresh(existing)
        return {"success": True, "data": _format_fish_count(existing), "action": "updated"}
    else:
        # Buat record baru
        fish_count = FishCount(
            id=generate_cuid(),
            session_id=session_id,
            species_name=species_name,
            total_count=int(count),
            detected_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(fish_count)
        db.commit()
        db.refresh(fish_count)
        return {"success": True, "data": _format_fish_count(fish_count), "action": "created"}


# ==========================
# POST /api/fish-counts/batch — simpan banyak spesies sekaligus
# Lebih efisien daripada POST satu-satu per spesies
# ==========================
@router.post("/batch", status_code=status.HTTP_201_CREATED)
def save_fish_count_batch(
    body: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Simpan atau update banyak spesies sekaligus dalam satu request.
    Lebih efisien untuk YOLO yang mendeteksi banyak spesies per frame.

    Payload:
        session_id : str
        counts     : [{ species_name: str, count: int }, ...]
    """
    session_id = body.get("session_id") or body.get("sessionId")
    counts     = body.get("counts", [])

    if not session_id or not counts:
        raise HTTPException(
            status_code=400,
            detail="session_id dan counts wajib diisi"
        )

    # Verifikasi sesi ada
    session = db.query(MonitoringSession).filter(
        MonitoringSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    now = datetime.now(timezone.utc)
    results = []

    for item in counts:
        species_name = item.get("species_name") or item.get("speciesName")
        count        = int(item.get("count", 0))

        if not species_name or count <= 0:
            continue

        existing = db.query(FishCount).filter(
            FishCount.session_id  == session_id,
            FishCount.species_name == species_name,
        ).first()

        if existing:
            existing.total_count += count
            existing.updated_at   = now
            results.append(_format_fish_count(existing))
        else:
            fish_count = FishCount(
                id=generate_cuid(),
                session_id=session_id,
                species_name=species_name,
                total_count=count,
                detected_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(fish_count)
            results.append(_format_fish_count(fish_count))

    db.commit()
    return {
        "success": True,
        "data": results,
        "total": len(results),
    }


# ==========================
# GET /api/fish-counts/session/{session_id}
# Semua spesies dalam satu sesi — dipakai Analytics
# ==========================
@router.get("/session/{session_id}")
def get_fish_counts_by_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET semua fish counts dalam satu sesi, diurutkan dari terbanyak.
    Digunakan halaman Analytics untuk chart Species Population.
    """
    counts = (
        db.query(FishCount)
        .filter(FishCount.session_id == session_id)
        .order_by(FishCount.total_count.desc())
        .all()
    )

    total_fish = sum(c.total_count for c in counts)

    return {
        "success": True,
        "data": {
            "sessionId": session_id,
            "totalFish": total_fish,
            "speciesCount": len(counts),
            "counts": [_format_fish_count(c) for c in counts],
        },
    }


# ==========================
# GET /api/fish-counts/summary — ringkasan semua sesi
# ==========================
@router.get("/summary")
def get_fish_counts_summary(
    limit: int = 10,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET ringkasan total ikan per spesies dari semua sesi.
    Digunakan halaman Historical untuk overview populasi.
    """
    summary = (
        db.query(
            FishCount.species_name,
            func.sum(FishCount.total_count).label("total"),
        )
        .group_by(FishCount.species_name)
        .order_by(func.sum(FishCount.total_count).desc())
        .limit(limit)
        .all()
    )

    grand_total = db.query(func.sum(FishCount.total_count)).scalar() or 0

    return {
        "success": True,
        "data": {
            "grandTotal": int(grand_total),
            "species": [
                {
                    "speciesName": row.species_name,
                    "total": int(row.total),
                    "percentage": round(int(row.total) / int(grand_total) * 100, 1)
                    if grand_total > 0 else 0,
                }
                for row in summary
            ],
        },
    }


# ==========================
# GET /api/fish-counts — list dengan pagination
# ==========================
@router.get("")
def get_fish_counts(
    page: int = 1,
    limit: int = 20,
    session_id: Optional[str] = None,
    species_name: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    GET list fish counts dengan pagination dan filter opsional.
    """
    skip  = (page - 1) * limit
    query = db.query(FishCount)

    if session_id:
        query = query.filter(FishCount.session_id == session_id)
    if species_name:
        query = query.filter(FishCount.species_name.contains(species_name))

    total  = query.count()
    counts = (
        query.order_by(FishCount.total_count.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": [_format_fish_count(c) for c in counts],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": (total + limit - 1) // limit,
        },
    }


# ==========================
# Helper
# ==========================
def _format_fish_count(c: FishCount) -> dict:
    return {
        "id": c.id,
        "sessionId": c.session_id,
        "speciesName": c.species_name,
        "totalCount": c.total_count,
        "detectedAt": c.detected_at.isoformat(),
        "createdAt": c.created_at.isoformat(),
        "updatedAt": c.updated_at.isoformat(),
    }