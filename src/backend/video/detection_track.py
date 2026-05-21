import cv2
import time
import asyncio
import logging
import numpy as np
import queue
import threading
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

# Performance counters
frame_count = 0
inference_count = 0
last_fps_time = time.time()
last_infer_time = time.time()
current_fps = 0.0
current_infer_fps = 0.0


class RtspDetectionTrack(VideoStreamTrack):

    def __init__(self, video_source_track):
        super().__init__()
        self.src = video_source_track
        self.frame_skip = 0
        self.skip_n = 0  # 0 = process every frame
        self.last_dets: List[Tuple[int, int, int, int, float, str]] = []

        self.size = (RESIZE_WIDTH, RESIZE_HEIGHT) if (RESIZE_WIDTH and RESIZE_HEIGHT) else None
        self.conf = YOLO_CONF_THRESHOLD
        self.iou = YOLO_IOU_THRESHOLD
        self.max_det = YOLO_MAX_DETECTIONS

        # Database saving
        self.last_save_time = time.time()
        self.save_task: Optional[asyncio.Task] = None

        # Recording support with background thread for non-blocking writes
        self.recording = False
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.frame_queue: Optional[queue.Queue] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.stop_writer_thread = False

    async def recv(self) -> VideoFrame:
        global frame_count, last_fps_time, current_fps
        global inference_count, last_infer_time, current_infer_fps

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
                inference_count += 1
                now = time.time()
                if now - last_infer_time >= 1.0:
                    current_infer_fps = inference_count / (now - last_infer_time)
                    inference_count = 0
                    last_infer_time = now

        self.frame_skip += 1

        # Draw overlay
        for (x1, y1, x2, y2, conf, name) in self.last_dets:
            cv2.rectangle(img, (x1, y1), (x2, y2), (50, 220, 50), 3)
            label = f"{name} {conf:.2f}"
            cv2.putText(img, label, (x1, max(0, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Performance text
        frame_count += 1
        now = time.time()
        if now - last_fps_time >= 1.0:
            current_fps = frame_count / (now - last_fps_time)
            frame_count = 0
            last_fps_time = now

        device = get_device_info()
        cv2.putText(img, f"FPS: {current_fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.putText(img, f"Inference: {current_infer_fps:.1f}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(img, f"Device: {device}", (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

        if self.recording and self.frame_queue is not None:
            try:
                self.frame_queue.put_nowait(img.copy())
            except queue.Full:
                pass

        img = img.astype(np.uint8)
        out = VideoFrame.from_ndarray(img, format="bgr24")
        out.pts = frame.pts
        out.time_base = frame.time_base
        return out

    def _video_writer_thread(self):
        logger.info("Video writer thread started")
        frames_written = 0

        while not self.stop_writer_thread or (
            self.frame_queue is not None and not self.frame_queue.empty()
        ):
            try:
                if self.frame_queue is not None:
                    frame = self.frame_queue.get(timeout=0.5)

                    if self.video_writer is not None:
                        self.video_writer.write(frame)
                        frames_written += 1

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error writing frame to video: {e}")

        logger.info(f"Video writer thread stopped. Frames written: {frames_written}")

    def start_recording(self, video_writer: cv2.VideoWriter):
        self.recording = True
        self.video_writer = video_writer
        self.stop_writer_thread = False

        # Create queue for frames (max 30 frames buffered)
        self.frame_queue = queue.Queue(maxsize=30)

        # Start background writer thread
        self.writer_thread = threading.Thread(target=self._video_writer_thread, daemon=True)
        self.writer_thread.start()

        logger.info(f"Started recording with background thread at full FPS (non-blocking)")

    def stop_recording(self):
        self.recording = False

        # Stop the writer thread
        self.stop_writer_thread = True

        # Wait for queue to drain and thread to finish
        if self.writer_thread is not None:
            logger.info("Waiting for video writer thread to finish...")
            self.writer_thread.join(timeout=10.0)

            if self.writer_thread.is_alive():
                logger.warning("Video writer thread did not finish in time")

            self.writer_thread = None

        # Release video writer
        if self.video_writer is not None:
            try:
                self.video_writer.release()
                logger.info("Video writer released successfully")
            except Exception as e:
                logger.error(f"Error releasing video writer: {e}")
            finally:
                self.video_writer = None

        # Clear queue
        self.frame_queue = None

        logger.info("Stopped recording video frames")


def get_fps() -> float:
    return current_fps


def get_inference_fps() -> float:
    return current_infer_fps