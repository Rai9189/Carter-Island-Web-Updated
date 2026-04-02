# main.py
import os
import re
import cv2
import time
import json
import torch
import asyncio
import logging
import numpy as np
import uuid
import httpx
from typing import Dict, Set, Optional, Callable, List, Tuple
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame

# ==========================
# Config & Logging
# ==========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("carter-backend")

# ---- Streaming / encoder prefs (bisa override via ENV) ----
RTSP_URL = os.getenv("RTSP_URL", "rtsp://192.168.2.2:8554/cam")
RTSP_TRANSPORT = os.getenv("RTSP_TRANSPORT", "udp")
TARGET_FPS = int(os.getenv("TARGET_FPS", "30"))
RESIZE_WIDTH = int(os.getenv("RESIZE_WIDTH", "1280"))
RESIZE_HEIGHT = int(os.getenv("RESIZE_HEIGHT", "720"))

# Bitrate control
MAX_BITRATE_KBPS_DEFAULT = int(os.getenv("MAX_BITRATE_KBPS", "4500"))
MIN_BITRATE_KBPS_FLOOR   = int(os.getenv("MIN_BITRATE_KBPS", "2500"))
BITRATE_REAPPLY_SEC      = float(os.getenv("BITRATE_REAPPLY_SEC", "4.0"))
# Codec preference ("h264" / "vp8")
PREFER_CODEC = os.getenv("PREFER_CODEC", "h264").lower()

DISABLE_TWCC_REM = os.getenv("DISABLE_TWCC_REMB", "1") == "1"

# ---- Database Saving Config ----
SAVE_DETECTIONS_ENABLED = os.getenv("SAVE_DETECTIONS_ENABLED", "true").lower() == "true"
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
SAVE_INTERVAL_SECONDS = float(os.getenv("SAVE_INTERVAL_SECONDS", "5.0"))  # Simpan setiap 5 detik
MIN_DETECTIONS_TO_SAVE = int(os.getenv("MIN_DETECTIONS_TO_SAVE", "1"))  # Minimal 1 ikan terdeteksi

# ==========================
# Globals & Performance
# ==========================
peer_connections: Dict[str, RTCPeerConnection] = {}
active_connections: Set[WebSocket] = set()
bitrate_tasks: Dict[str, asyncio.Task] = {}

custom_model = None
device_info = "CPU"
inference_executor = ThreadPoolExecutor(max_workers=2)

# Database saving
http_client: Optional[httpx.AsyncClient] = None
streaming_session_id: str = str(uuid.uuid4())  # ID unik untuk sesi streaming ini

# Perf counters
frame_count = 0
inference_count = 0
last_fps_time = time.time()
last_infer_time = time.time()
current_fps = 0.0
current_infer_fps = 0.0

# ==========================
# Model Loader (Ultralytics YOLO)
# ==========================
def load_custom_model():
    global custom_model, device_info
    try:
        cuda = torch.cuda.is_available()
        if cuda:
            cuda_ver = getattr(getattr(torch, "version", None), "cuda", None)
            device_info = f"CUDA {cuda_ver or 'unknown'} - {torch.cuda.get_device_name(0)}"
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
            torch.cuda.empty_cache()
        else:
            device_info = "CPU"

        model_path = os.path.join(os.path.dirname(__file__), "models", "16sept.pt")
        if not os.path.exists(model_path):
            logger.warning(f"Model not found at {model_path}, running passthrough (no detection).")
            custom_model = None
            return

        from ultralytics import YOLO
        custom_model = YOLO(model_path)
        if cuda:
            custom_model.to('cuda')

        # warmup
        dummy = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        for _ in range(2):
            _ = custom_model(dummy, verbose=False, device='cuda' if cuda else 'cpu')
        if cuda:
            torch.cuda.synchronize()
        logger.info("YOLO model loaded & warmed up.")
    except Exception as e:
        logger.exception(f"Failed to load model: {e}")
        custom_model = None
        device_info = "Error"

# ==========================
# Database Saving Functions
# ==========================
async def save_detections_to_db(
    detections: List[Tuple[int, int, int, int, float, str]],
    frame_number: Optional[int] = None
) -> bool:
    """
    Simpan hasil deteksi ke database melalui API Next.js

    Args:
        detections: List of (x1, y1, x2, y2, confidence, class_name)
        frame_number: Nomor frame (opsional)

    Returns:
        bool: True jika berhasil, False jika gagal
    """
    if not SAVE_DETECTIONS_ENABLED or not http_client:
        return False

    if len(detections) < MIN_DETECTIONS_TO_SAVE:
        return False

    try:
        # Format data untuk API
        detection_details = []
        for (x1, y1, x2, y2, conf, name) in detections:
            detection_details.append({
                "className": name,
                "confidence": float(conf),
                "boundingBox": {
                    "x1": float(x1),
                    "y1": float(y1),
                    "x2": float(x2),
                    "y2": float(y2)
                }
            })

        payload = {
            "sessionId": streaming_session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "fishCount": len(detections),
            "frameNumber": frame_number,
            "detections": detection_details
        }

        # Kirim ke API
        response = await http_client.post(
            f"{API_BASE_URL}/api/detections",
            json=payload,
            timeout=5.0
        )

        if response.status_code == 201:
            logger.info(f"✓ Saved {len(detections)} detections to database (frame {frame_number})")
            return True
        else:
            logger.warning(f"Failed to save detections: HTTP {response.status_code} - {response.text}")
            return False

    except httpx.TimeoutException:
        logger.warning("Timeout while saving detections to database")
        return False
    except Exception as e:
        logger.error(f"Error saving detections to database: {e}")
        return False

# ==========================
# Bitrate helpers (aiortc + SDP munging)
# ==========================
def _insert_bitrate_and_xgoogle(sdp: str, kbps: int, fps: int) -> str:

    lines = sdp.splitlines()
    out = []
    in_video = False
    inserted_b = False

    min_kb = max(300, min(kbps, max(MIN_BITRATE_KBPS_FLOOR, kbps // 4)))
    for line in lines:
        out.append(line)

        if line.startswith("m=video"):
            in_video = True
            inserted_b = False
            continue

        if in_video and line.startswith("c=") and not inserted_b:
            out.append(f"b=AS:{kbps}")
            inserted_b = True

        if in_video and line.startswith("a=fmtp:"):
            if "x-google-max-bitrate" not in line:
                out[-1] = (
                    line
                    + f";x-google-start-bitrate={kbps}"
                    + f";x-google-max-bitrate={kbps}"
                    + f";x-google-min-bitrate={min_kb}"
                    + f";max-fs=8160;max-fr={fps}"
                )

        if in_video and line.startswith("m=") and not line.startswith("m=video"):
            in_video = False

    return "\r\n".join(out) + "\r\n"

def _prefer_codec(sdp: str, codec: str = "H264") -> str:
    codec = codec.upper()
    lines = sdp.splitlines()
    try:
        # mapping payload by codec
        pt_by_codec = {}
        for l in lines:
            if l.startswith("a=rtpmap:"):
                parts = l.split()
                pt = parts[0].split(":")[1]
                name = parts[1].split("/")[0].upper()
                pt_by_codec.setdefault(name, []).append(pt)

        m_idx = next(i for i, l in enumerate(lines) if l.startswith("m=video"))
        parts = lines[m_idx].split()
        header, pts = parts[:3], parts[3:]
        preferred = pt_by_codec.get(codec, [])
        if not preferred:
            return sdp
        new_pts = [pt for pt in preferred if pt in pts] + [pt for pt in pts if pt not in preferred]
        lines[m_idx] = " ".join(header + new_pts)
        return "\r\n".join(lines) + "\r\n"
    except Exception:
        return sdp

def _strip_twcc_and_remb(sdp: str) -> str:

    lines = sdp.splitlines()
    out = []
    for l in lines:
        if l.startswith("a=rtcp-fb:") and ("transport-cc" in l or "goog-remb" in l):
            continue
        if l.startswith("a=extmap:") and "transport-cc" in l:
            continue
        out.append(l)
    return "\r\n".join(out) + "\r\n"

async def set_sender_bitrate(sender, max_bitrate_bps: int, max_fps: int = 30) -> Optional[Callable[[str], str]]:
   
    try:
        get_params = getattr(sender, "getParameters", None)
        set_params = getattr(sender, "setParameters", None)
        if callable(get_params) and callable(set_params):
            params = get_params()
            if not getattr(params, "encodings", None):
                params.encodings = [{}] # type: ignore
            enc = params.encodings[0] # type: ignore
            enc["maxBitrate"] = int(max_bitrate_bps)
            enc["maxFramerate"] = int(max_fps)
            await set_params(params) # type: ignore
            return None
        
        return lambda sdp: _insert_bitrate_and_xgoogle(sdp, max_bitrate_bps // 1000, max_fps)
    except Exception as e:
        logger.warning(f"set_sender_bitrate fallback: {e}")
        return lambda sdp: _insert_bitrate_and_xgoogle(sdp, max_bitrate_bps // 1000, max_fps)

async def periodic_reapply_bitrate(client_id: str, sender, bps: int, fps: int):

    try:
        while client_id in peer_connections:
            await set_sender_bitrate(sender, bps, fps)
            await asyncio.sleep(BITRATE_REAPPLY_SEC)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"bitrate reapply err: {e}")

def tune_answer_sdp(raw_sdp: str, kbps: int, fps: int, prefer: str, disable_twcc: bool) -> str:
    sdp = raw_sdp
    # Force codec
    if prefer == "h264":
        sdp = _prefer_codec(sdp, "H264")
    elif prefer == "vp8":
        sdp = _prefer_codec(sdp, "VP8")

    sdp = _insert_bitrate_and_xgoogle(sdp, kbps, fps)

    if disable_twcc:
        sdp = _strip_twcc_and_remb(sdp)

    return sdp

# ==========================
# RTSP Player & Detection Track
# ==========================
def make_rtsp_player(transport: str) -> MediaPlayer:

    opts = {
        "rtsp_transport": transport,
        "fflags": "nobuffer",
        "flags": "low_delay",
        "max_delay": "0",
        "reorder_queue_size": "0",
        "probesize": "32",
        "analyzeduration": "0",
        "rw_timeout": "2000000",
        "stimeout": "2000000",
        "fflags+": "flush_packets",
    }
    logger.info(f"Opening RTSP: {RTSP_URL} (transport={transport})")
    return MediaPlayer(RTSP_URL, format="rtsp", options=opts)

class RtspDetectionTrack(VideoStreamTrack):
    def __init__(self, video_source_track):
        super().__init__()
        self.src = video_source_track
        self.frame_skip = 0
        self.skip_n = 0  # 0 = proses tiap frame
        self.last_dets = []

        self.size = (RESIZE_WIDTH, RESIZE_HEIGHT) if (RESIZE_WIDTH and RESIZE_HEIGHT) else None
        self.conf = 0.45
        self.iou = 0.5
        self.max_det = 30

        # Database saving
        self.last_save_time = time.time()
        self.save_task: Optional[asyncio.Task] = None

    async def recv(self) -> VideoFrame:
        global frame_count, last_fps_time, current_fps
        global inference_count, last_infer_time, current_infer_fps

        frame: VideoFrame = await self.src.recv()
        img = frame.to_ndarray(format="bgr24")

        if self.size:
            img = cv2.resize(img, self.size, interpolation=cv2.INTER_LINEAR)

        do_infer = (self.frame_skip % (self.skip_n + 1) == 0)
        if custom_model is not None and do_infer:
            try:
                res = custom_model(
                    img,
                    verbose=False,
                    conf=self.conf,
                    iou=self.iou,
                    max_det=self.max_det,
                    device='cuda' if torch.cuda.is_available() else 'cpu'
                )
                dets = []
                for r in res:
                    if getattr(r, "boxes", None) is None:
                        continue
                    for box in r.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0].cpu().numpy())
                        cls = int(box.cls[0].cpu().numpy())
                        name = f"Class_{cls}"
                        if hasattr(custom_model, "names") and cls < len(custom_model.names):
                            name = custom_model.names[cls]
                        dets.append((int(x1), int(y1), int(x2), int(y2), conf, name))
                self.last_dets = dets

                # Simpan deteksi ke database secara periodik
                now = time.time()
                if (SAVE_DETECTIONS_ENABLED and
                    len(dets) >= MIN_DETECTIONS_TO_SAVE and
                    now - self.last_save_time >= SAVE_INTERVAL_SECONDS):
                    # Simpan tanpa blocking
                    if self.save_task is None or self.save_task.done():
                        self.save_task = asyncio.create_task(
                            save_detections_to_db(dets.copy(), self.frame_skip)
                        )
                        self.last_save_time = now

            except Exception as e:
                logger.warning(f"infer err: {e}")
            finally:
                inference_count += 1
                now = time.time()
                if now - last_infer_time >= 1.0:
                    current_infer_fps = inference_count / (now - last_infer_time)
                    inference_count = 0
                    last_infer_time = now

        self.frame_skip += 1

        # draw overlay
        for (x1, y1, x2, y2, conf, name) in self.last_dets:
            cv2.rectangle(img, (x1, y1), (x2, y2), (50, 220, 50), 3)
            label = f"{name} {conf:.2f}"
            cv2.putText(img, label, (x1, max(0, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # perf text
        frame_count += 1
        now = time.time()
        if now - last_fps_time >= 1.0:
            current_fps = frame_count / (now - last_fps_time)
            frame_count = 0
            last_fps_time = now

        cv2.putText(img, f"FPS: {current_fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.putText(img, f"Inference: {current_infer_fps:.1f}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(img, f"Device: {device_info}", (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

        img = img.astype(np.uint8)
        out = VideoFrame.from_ndarray(img, format="bgr24")
        out.pts = frame.pts
        out.time_base = frame.time_base
        return out

# ==========================
# FastAPI App + Lifespan
# ==========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, streaming_session_id
    logger.info("Starting Carter Island Backend...")
    load_custom_model()

    # Initialize HTTP client untuk database saving
    if SAVE_DETECTIONS_ENABLED:
        http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        logger.info(f"Database saving enabled - Session ID: {streaming_session_id}")
        logger.info(f"API endpoint: {API_BASE_URL}/api/detections")
        logger.info(f"Save interval: {SAVE_INTERVAL_SECONDS}s")
    else:
        logger.info("Database saving disabled")

    yield

    logger.info("Shutting down...")
    try:
        # Close HTTP client
        if http_client:
            await http_client.aclose()

        for cid in list(peer_connections.keys()):
            pc = peer_connections.pop(cid, None)
            if pc:
                await pc.close()
        for t in bitrate_tasks.values():
            t.cancel()
        inference_executor.shutdown(wait=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as e:
        logger.warning(f"shutdown err: {e}")

app = FastAPI(title="Carter Island GPU-Optimized Stream Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# WebSocket / WS Signaling
# ==========================
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"WS client {client_id} connected")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "offer":
                await handle_offer(websocket, client_id, msg)
            elif msg.get("type") == "ice-candidate":
                # browser -> server ICE
                pass
    except WebSocketDisconnect:
        logger.info(f"WS disconnect {client_id}")
    except Exception as e:
        logger.exception(f"WS error {client_id}: {e}")
    finally:
        active_connections.discard(websocket)
        await cleanup_pc(client_id)

async def handle_offer(websocket: WebSocket, client_id: str, message: dict):
    # Preferensi juga bisa dikirim di body offer dari FE
    offer_sdp = message["sdp"]
    pref_codec = (message.get("codec") or PREFER_CODEC).lower()
    max_kbps = int(message.get("maxBitrateKbps") or MAX_BITRATE_KBPS_DEFAULT)
    fps = int(message.get("fps") or TARGET_FPS)

    # Transport RTSP bisa lewat query params ws (...?transport=tcp)
    qp = websocket.query_params
    transport = (qp.get("transport") or RTSP_TRANSPORT).lower()

    # cleanup existing
    await cleanup_pc(client_id)

    pc = RTCPeerConnection()
    peer_connections[client_id] = pc

    # RTSP source
    player = make_rtsp_player(transport)
    if not player.video:
        raise RuntimeError("RTSP player has no video track")
    det_track = RtspDetectionTrack(player.video)

    sender = pc.addTrack(det_track)

    @pc.on("connectionstatechange")
    async def _on_state():
        logger.info(f"{client_id} state: {pc.connectionState}")
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await cleanup_pc(client_id)

    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))

    sdp_munger = await set_sender_bitrate(sender, max_kbps * 1000, fps)

    # create answer
    answer = await pc.createAnswer()
    tuned = tune_answer_sdp(
        raw_sdp=answer.sdp,
        kbps=max_kbps,
        fps=fps,
        prefer=pref_codec,
        disable_twcc=DISABLE_TWCC_REM,
    )
    answer = RTCSessionDescription(sdp=tuned, type=answer.type)
    await pc.setLocalDescription(answer)

    task = asyncio.create_task(periodic_reapply_bitrate(client_id, sender, max_kbps * 1000, fps))
    bitrate_tasks[client_id] = task

    await websocket.send_text(json.dumps({"type": "answer", "sdp": pc.localDescription.sdp}))
    logger.info(
        f"Answer -> {client_id} | codec={pref_codec}, {max_kbps}kbps, fps={fps}, rtsp={transport}, "
        f"twcc_remb_disabled={DISABLE_TWCC_REM}"
    )

async def cleanup_pc(client_id: str):
    task = bitrate_tasks.pop(client_id, None)
    if task:
        task.cancel()
    pc = peer_connections.pop(client_id, None)
    if pc:
        try:
            for s in pc.getSenders():
                try:
                    if s.track:
                        s.track.stop()
                except Exception:
                    pass
            await pc.close()
        except Exception:
            pass
        logger.info(f"PC {client_id} closed")

# ==========================
# REST Endpoints
# ==========================
@app.get("/")
async def root():
    return {
        "message": "Carter Island GPU-Optimized Backend",
        "device": device_info,
        "cuda_available": torch.cuda.is_available(),
        "model_loaded": custom_model is not None,
        "rtsp_url": RTSP_URL,
    }

@app.get("/api/health")
async def health():
    gpu = {}
    if torch.cuda.is_available():
        gpu = {
            "gpu_name": torch.cuda.get_device_name(0),
            "mem_total": torch.cuda.get_device_properties(0).total_memory,
            "mem_alloc": torch.cuda.memory_allocated(0),
            "mem_reserved": torch.cuda.memory_reserved(0),
        }

    model_info = {
        "model_loaded": custom_model is not None,
        "model_type": type(custom_model).__name__ if custom_model else None
    }
    if custom_model and hasattr(custom_model, "names"):
        model_info["classes"] = custom_model.names
        model_info["num_classes"] = len(custom_model.names)

    return {
        "status": "healthy",
        "device": device_info,
        "model_info": model_info,
        "fps": current_fps,
        "inference_fps": current_infer_fps,
        "active_peer_connections": len(peer_connections),
        "cuda": torch.cuda.is_available(),
        "torch": torch.__version__,
        "gpu": gpu,
    }

@app.get("/api/performance")
async def perf():
    return {
        "fps": round(current_fps, 2),
        "inference_fps": round(current_infer_fps, 2),
        "active_peer_connections": len(peer_connections),
        "device": device_info,
        "model_loaded": custom_model is not None,
        "cuda_available": torch.cuda.is_available(),
    }

@app.get("/api/model-info")
async def model_info():
    if not custom_model:
        return {"model_loaded": False}
    info = {
        "model_loaded": True,
        "model_type": type(custom_model).__name__,
        "device": device_info
    }
    if hasattr(custom_model, "names"):
        info["classes"] = custom_model.names
        info["num_classes"] = len(custom_model.names)
    return info

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False
    )
