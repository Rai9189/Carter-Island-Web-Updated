"""
Perekaman video (T7): durasi = waktu nyata, file bisa di-seek, dan file
tetap terbaca walau proses mati sebelum stop. Tanpa RTSP/YOLO — frame
sintetis dimasukkan langsung ke antrean rekaman.
"""
import os
import shutil
import time

import av
import numpy as np

from video.detection_track import RtspDetectionTrack


def _feed(track, seconds, fps_pattern=(30, 5, 15)):
    """Kirim frame dengan FPS naik-turun selama `seconds` detik."""
    img = np.zeros((720, 1280, 3), np.uint8)
    end = time.monotonic() + seconds
    i = 0
    while time.monotonic() < end:
        img[:] = (i * 7) % 255
        track.enqueue_recording_frame(img)
        time.sleep(1 / fps_pattern[(i // 10) % len(fps_pattern)])
        i += 1


def _probe(path):
    with av.open(path) as c:
        s = c.streams.video[0]
        frames = list(c.decode(s))
        dur = float(frames[-1].pts * s.time_base) if frames else 0.0
        return c.duration, len(frames), dur


def test_duration_matches_wall_clock_and_is_seekable(tmp_path):
    path = str(tmp_path / "rec.mp4")
    track = RtspDetectionTrack(None)
    track.start_recording(path)
    _feed(track, 4.0)
    assert track.stop_recording() is True
    assert track.recording is False

    _, n, dur = _probe(path)
    assert n > 20
    assert abs(dur - 4.0) < 0.5, dur  # dulu: 210 frame / 10 fps → durasi salah

    # keyframe kedua (frame ke-30) jatuh ~detik 3 → seek ke 3.6 harus mendarat
    # di keyframe itu, bukan kembali ke awal file
    with av.open(path) as c:
        s = c.streams.video[0]
        c.seek(int(3.6 / s.time_base), stream=s, backward=True)
        first = next(c.decode(s))
        assert float(first.pts * s.time_base) >= 2.5


def test_file_readable_without_stop(tmp_path):
    """Simulasi crash: salin file saat rekaman masih jalan, salinan harus bisa diputar."""
    path = str(tmp_path / "rec.mp4")
    track = RtspDetectionTrack(None)
    track.start_recording(path)
    _feed(track, 4.5, fps_pattern=(15,))  # keyframe di detik 0, 2, 4 → ≥ 2 fragmen selesai
    time.sleep(0.3)
    crashed = str(tmp_path / "crashed.mp4")
    shutil.copy(path, crashed)
    track.stop_recording()

    _, n, dur = _probe(crashed)
    assert n >= 30 and dur >= 1.5, (n, dur)


def test_stop_without_start_is_noop():
    assert RtspDetectionTrack(None).stop_recording() is True
