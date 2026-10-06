import av
import cv2
import time
import asyncio
import logging
import numpy as np
import queue
import threading
from fractions import Fraction
from typing import Optional, List, Tuple
from aiortc import VideoStreamTrack
from av import VideoFrame

from config import (
    RESIZE_WIDTH,
    RESIZE_HEIGHT,
    YOLO_CONF_THRESHOLD,
    YOLO_IOU_THRESHOLD,
    YOLO_MAX_DETECTIONS,
    SAVE_DETECTIONS_ENABLED,
    SAVE_INTERVAL_SECONDS,
    MIN_DETECTIONS_TO_SAVE
)
from models.yolo_detector import run_inference, get_device_info
from database.crud.detections import save_detection_to_db  # GANTI: dari database.detections

logger = logging.getLogger("carter-backend")

# Rekaman: H.264 (libx264) di MP4 terfragmentasi — file tetap bisa diputar
# sampai fragmen terakhir walau backend mati sebelum stop.
RECORD_TIME_BASE = Fraction(1, 1000)  # pts dalam milidetik jam dinding
RECORD_MOVFLAGS = "frag_keyframe+empty_moov+default_base_moof"
RECORD_GOP = 30  # keyframe tiap 30 frame = batas fragmen; crash kehilangan < 1 fragmen
RECORD_QUEUE_SIZE = 60


def write_recording(filepath: str, frames: "queue.Queue") -> int:
    """
    Tulis frame (monotonic_time, bgr_ndarray) dari antrean ke MP4 sampai
    menerima None. Hanya fungsi ini yang membuka, menulis, dan menutup file,
    jadi tidak ada release dari thread lain saat encoder masih dipakai.
    pts diambil dari jam dinding → durasi video = durasi rekaman nyata walau
    FPS naik-turun atau frame dibuang saat antrean penuh.
    """
    # flush_packets: tiap fragmen langsung ke disk (tanpa ini tertahan di buffer → hilang saat crash)
    container = av.open(filepath, mode="w", format="mp4",
                        options={"movflags": RECORD_MOVFLAGS, "flush_packets": "1"})
    stream = None
    t0 = 0.0
    last_pts = -1
    written = 0
    try:
        while True:
            item = frames.get()
            if item is None:
                break
            t, img = item
            if stream is None:
                h, w = img.shape[:2]
                stream = container.add_stream("libx264", rate=30)
                stream.width, stream.height = w - w % 2, h - h % 2  # yuv420p wajib genap
                stream.pix_fmt = "yuv420p"
                stream.time_base = RECORD_TIME_BASE
                stream.codec_context.time_base = RECORD_TIME_BASE
                stream.codec_context.gop_size = RECORD_GOP
                stream.options = {"preset": "ultrafast", "tune": "zerolatency"}
                t0 = t
            pts = max(int((t - t0) * 1000), last_pts + 1)
            last_pts = pts
            frame = VideoFrame.from_ndarray(img[:stream.height, :stream.width], format="bgr24")
            frame.pts = pts
            frame.time_base = RECORD_TIME_BASE
            container.mux(stream.encode(frame))
            written += 1
        if stream is not None:
            container.mux(stream.encode())  # flush encoder
    except Exception:
        logger.exception(f"Error writing recording {filepath}")
    finally:
        container.close()
    logger.info(f"Video writer stopped: {filepath} ({written} frames, {last_pts / 1000:.1f}s)")
    return written


class RtspDetectionTrack(VideoStreamTrack):

    def __init__(self, video_source_track):
        super().__init__()
        self.src = video_source_track
        self.frame_skip = 0
        self.skip_n = 0  # 0 = process every frame
        self.last_dets: List[Tuple[int, int, int, int, float, str]] = []

        # Performance counters per track (bukan global) agar FPS tiap client
        # tidak saling menjumlah saat ada >1 client terhubung
        self.frame_count = 0
        self.inference_count = 0
        self.last_fps_time = time.time()
        self.last_infer_time = time.time()
        self.current_fps = 0.0
        self.current_infer_fps = 0.0

        self.size = (RESIZE_WIDTH, RESIZE_HEIGHT) if (RESIZE_WIDTH and RESIZE_HEIGHT) else None
        self.conf = YOLO_CONF_THRESHOLD
        self.iou = YOLO_IOU_THRESHOLD
        self.max_det = YOLO_MAX_DETECTIONS

        # Database saving
        self.last_save_time = time.time()
        self.save_task: Optional[asyncio.Task] = None

        # Recording: frame dikirim ke thread penulis (write_recording) lewat antrean
        self.recording = False
        self.frame_queue: Optional[queue.Queue] = None
        self.writer_thread: Optional[threading.Thread] = None

    async def recv(self) -> VideoFrame:
        frame: VideoFrame = await self.src.recv()
        img = frame.to_ndarray(format="bgr24")

        if self.size:
            img = cv2.resize(img, self.size, interpolation=cv2.INTER_LINEAR)

        # Run inference
        do_infer = (self.frame_skip % (self.skip_n + 1) == 0)
        if do_infer:
            try:
                dets = run_inference(img, self.conf, self.iou, self.max_det)
                self.last_dets = dets

                # Save detections to database periodically
                now = time.time()
                if (SAVE_DETECTIONS_ENABLED and
                    len(dets) >= MIN_DETECTIONS_TO_SAVE and
                    now - self.last_save_time >= SAVE_INTERVAL_SECONDS):
                    # Save without blocking — langsung ke SQLAlchemy, tidak lewat HTTP
                    if self.save_task is None or self.save_task.done():
                        self.save_task = asyncio.create_task(
                            save_detection_to_db(dets.copy(), self.frame_skip)
                        )
                        self.last_save_time = now

            except Exception as e:
                logger.warning(f"Inference error: {e}")
            finally:
                self.inference_count += 1
                now = time.time()
                if now - self.last_infer_time >= 1.0:
                    self.current_infer_fps = self.inference_count / (now - self.last_infer_time)
                    self.inference_count = 0
                    self.last_infer_time = now

        self.frame_skip += 1

        # Draw overlay
        for (x1, y1, x2, y2, conf, name) in self.last_dets:
            cv2.rectangle(img, (x1, y1), (x2, y2), (50, 220, 50), 3)
            label = f"{name} {conf:.2f}"
            cv2.putText(img, label, (x1, max(0, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Performance text
        self.frame_count += 1
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.current_fps = self.frame_count / (now - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = now

        device = get_device_info()
        cv2.putText(img, f"FPS: {self.current_fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.putText(img, f"Inference: {self.current_infer_fps:.1f}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(img, f"Device: {device}", (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

        self.enqueue_recording_frame(img)

        img = img.astype(np.uint8)
        out = VideoFrame.from_ndarray(img, format="bgr24")
        out.pts = frame.pts
        out.time_base = frame.time_base
        return out

    def enqueue_recording_frame(self, img: np.ndarray):
        q = self.frame_queue
        if self.recording and q is not None:
            try:
                q.put_nowait((time.monotonic(), img.copy()))
            except queue.Full:
                pass  # encoder tertinggal: frame dibuang, durasi tetap benar (pts jam dinding)

    def start_recording(self, filepath: str):
        self.frame_queue = queue.Queue(maxsize=RECORD_QUEUE_SIZE)
        self.writer_thread = threading.Thread(
            target=write_recording, args=(filepath, self.frame_queue), daemon=True
        )
        self.writer_thread.start()
        self.recording = True
        logger.info(f"Started recording to {filepath}")

    def stop_recording(self, timeout: float = 10.0) -> bool:
        """
        Blocking (panggil lewat asyncio.to_thread). Kirim tanda selesai ke
        thread penulis lalu tunggu file ditutup. True bila file sudah final.
        """
        self.recording = False
        q, thread = self.frame_queue, self.writer_thread
        self.frame_queue = self.writer_thread = None
        if q is None or thread is None:
            return True
        try:
            q.put(None, timeout=timeout)  # penulis sedang menguras antrean, slot pasti terbuka
        except queue.Full:
            pass
        thread.join(timeout)
        if thread.is_alive():
            # File tetap ditutup oleh thread penulis sendiri begitu selesai
            logger.warning("Video writer belum selesai saat timeout; file difinalisasi di background")
            return False
        return True
