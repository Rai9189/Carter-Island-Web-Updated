"""
Helper untuk metrik performa sistem (CPU/GPU) di endpoint /api/performance.
"""
import logging
from typing import Optional
import psutil
import torch

logger = logging.getLogger("carter-backend")


# ==========================
# get_cpu_percent
# ==========================
def get_cpu_percent() -> float:
    """
    CPU utilization (%) sejak pemanggilan terakhir.

    interval=None (non-blocking) sengaja dipakai — endpoint ini di-poll
    berkala oleh dashboard dan berjalan di event loop async FastAPI;
    interval angka akan blocking event loop selama itu dan macetin
    request lain (termasuk WebRTC signaling).
    """
    return psutil.cpu_percent(interval=None)


# ==========================
# get_gpu_percent
# ==========================
# TODO(Jetson Orin): torch.cuda.utilization() / nvidia-smi dipakai di sini
# untuk dev machine (GPU discrete NVIDIA). Di Jetson Orin, GPU terintegrasi
# dan tidak termonitor lewat nvidia-smi biasa — perlu diganti/ditambah
# cabang pakai `tegrastats` atau `jtop` (package `jetson-stats`) saat
# deploy ke hardware Jetson.
def get_gpu_percent() -> Optional[float]:
    """
    GPU utilization (%) untuk dev machine. Return None kalau tidak ada
    CUDA GPU, atau kalau nvidia-smi/NVML tidak tersedia.
    """
    if not torch.cuda.is_available():
        return None

    try:
        return float(torch.cuda.utilization())
    except Exception as e:
        logger.warning(f"Gagal membaca GPU utilization: {e}")
        return None
