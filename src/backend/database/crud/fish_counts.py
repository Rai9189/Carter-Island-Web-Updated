"""
Agregasi fish_counts dari tabel detections.

fish_counts adalah turunan dari detections: dihitung ulang per sesi setiap
ada deteksi baru — di ROV (save_detection_to_db) dan di Base Station
(POST /api/sync/detections). Jadi angka di kedua sisi selalu konsisten
dengan deteksinya.

Metode hitung (keputusan 2026-09-25): PUNCAK PER FRAME.
YOLO belum pakai tracker, jadi ikan yang sama bisa muncul di banyak frame
sampel. total_ikan = jumlah terbanyak spesies itu yang terlihat bersamaan
dalam satu frame sampel — tidak pernah menghitung ikan yang sama dua kali,
tapi bisa kurang kalau ikan berbeda muncul bergantian.
Satu frame sampel = semua deteksi dengan (detected_at, frame_number) sama;
save_detection_to_db menyimpan satu frame dengan detected_at yang sama.
"""
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Detection, FishCount
from core.cuid import generate_cuid


def recompute_fish_counts(db: Session, session_id: str) -> None:
    """
    Hitung ulang fish_counts satu sesi dari detections (belum di-commit).
    Spesies yang tidak punya deteksi tidak disentuh.
    """
    per_frame = (
        db.query(
            Detection.species_name.label("species_name"),
            Detection.detected_at.label("detected_at"),
            func.count(Detection.id).label("n"),
        )
        .filter(Detection.session_id == session_id)
        .group_by(Detection.species_name, Detection.detected_at, Detection.frame_number)
        .subquery()
    )
    peaks = (
        db.query(
            per_frame.c.species_name,
            func.max(per_frame.c.n),
            func.min(per_frame.c.detected_at),
        )
        .group_by(per_frame.c.species_name)
        .all()
    )

    existing = {
        fc.species_name: fc
        for fc in db.query(FishCount).filter(FishCount.session_id == session_id).all()
    }
    now = datetime.now(timezone.utc)

    for species_name, peak, first_seen in peaks:
        fc = existing.get(species_name)
        if fc:
            if fc.total_ikan != peak:
                fc.total_ikan = peak
                fc.updated_at = now
        else:
            db.add(FishCount(
                id=generate_cuid(),
                session_id=session_id,
                species_name=species_name,
                total_ikan=peak,
                waktu_deteksi=first_seen,
                created_at=now,
                updated_at=now,
            ))
