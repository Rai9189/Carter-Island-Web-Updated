"""
CUID generator untuk Python.
Prisma menggunakan @default(cuid()) — kita perlu format yang sama
agar ID yang dibuat Python konsisten dengan ID dari Prisma.

Format cuid: c + timestamp + fingerprint + random
Contoh: clh3qz8x20000356ms8vfg2rx
"""
import time
import random
import string
import os


# Karakter yang dipakai cuid (lowercase alphanumeric)
_ALPHABET = string.ascii_lowercase + string.digits
_BASE = 36
_BLOCK_SIZE = 4
_DISCRETE_VALUES = _BASE ** _BLOCK_SIZE  # 1679616


def _to_base36(num: int) -> str:
    """Konversi integer ke base36 string."""
    if num == 0:
        return "0"
    result = ""
    while num:
        result = _ALPHABET[num % _BASE] + result
        num //= _BASE
    return result


def _pad(s: str, size: int) -> str:
    """Pad string dengan '0' di kiri sampai panjang tertentu."""
    return s.zfill(size)


# Counter global untuk menghindari collision dalam satu proses
_counter = random.randint(0, _DISCRETE_VALUES)


def generate_cuid() -> str:
    """
    Generate CUID yang kompatibel dengan format Prisma.
    
    Contoh output: clh3qz8x20000356ms8vfg2rx
    """
    global _counter

    # Timestamp dalam milliseconds
    timestamp = int(time.time() * 1000)
    ts_str = _pad(_to_base36(timestamp), 8)

    # Counter (increment, wrap around)
    _counter = (_counter + 1) % _DISCRETE_VALUES
    counter_str = _pad(_to_base36(_counter), _BLOCK_SIZE)

    # Fingerprint dari PID + hostname hash
    pid = os.getpid()
    hostname = os.uname().nodename if hasattr(os, "uname") else "host"
    fingerprint_num = (pid + sum(ord(c) for c in hostname)) % _DISCRETE_VALUES
    fingerprint_str = _pad(_to_base36(fingerprint_num), _BLOCK_SIZE)

    # Random block
    rand1 = random.randint(0, _DISCRETE_VALUES)
    rand2 = random.randint(0, _DISCRETE_VALUES)
    random_str = _pad(_to_base36(rand1), _BLOCK_SIZE) + _pad(_to_base36(rand2), _BLOCK_SIZE)

    return f"c{ts_str}{counter_str}{fingerprint_str}{random_str}"


if __name__ == "__main__":
    # Test generate beberapa CUID
    for _ in range(5):
        print(generate_cuid())