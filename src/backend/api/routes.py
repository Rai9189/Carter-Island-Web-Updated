"""
FastAPI routes for Carter Island Backend
"""
import json
import re
import torch
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import Dict, Set

from models.yolo_detector import get_model, get_model_info
from video.recording import (
    start_recording, stop_recording, is_recording, get_recording_info, NoActiveMissionError,
)
from webrtc.peer_connection import (
    handle_offer,
    cleanup_pc,
    get_peer_connections,
    get_detection_track,
    get_average_fps
)
from config import CORS_ORIGINS
from core.dependencies import get_current_user, get_user_from_token
from database.connection import SessionLocal
from core.system_metrics import get_cpu_percent, get_gpu_percent

logger = logging.getLogger("carter-backend")

# Active WebSocket connections
active_connections: Set[WebSocket] = set()

# client_id → {"user": pemilik, "ws": koneksi WebSocket yang aktif}.
# client_id dipakai sebagai kunci stream/rekaman DAN nama file rekaman.
client_connections: Dict[str, dict] = {}
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _owned_client(client_id: str, user: dict) -> None:
    """
    Kendali rekaman hanya untuk pemilik stream (atau ADMIN). Misi tetap data
    bersama (bisa ditutup siapa pun via PATCH sesi); yang dibatasi hanya
    kendali atas stream milik browser orang lain. 404 agar keberadaan
    client_id orang lain tidak bocor.
    """
    if not CLIENT_ID_RE.match(client_id):
        raise HTTPException(status_code=400, detail="client_id tidak valid")
    conn = client_connections.get(client_id)
    if conn is None or (conn["user"]["id"] != user["id"] and user["role"] != "ADMIN"):
        raise HTTPException(status_code=404, detail="Client not found or not streaming")


def setup_routes(app: FastAPI):
    """Setup all API routes"""

    @app.get("/")
    async def root():
        """Root endpoint with basic info"""
        model = get_model()
        return {
            "message": "Carter Island GPU-Optimized Backend",
            "device": get_device_info(),
            "cuda_available": torch.cuda.is_available(),
            "model_loaded": model is not None,
        }

    @app.get("/api/health")
    async def health():
        """
        Health check publik (tanpa login) untuk monitoring — sengaja ringkas.
        Detail GPU/versi/model ada di /api/performance & /api/model-info (wajib login).
        """
        fps, inference_fps = get_average_fps()
        return {
            "status": "healthy",
            "model_loaded": get_model() is not None,
            "fps": fps,
            "inference_fps": inference_fps,
        }

    @app.get("/api/performance")
    async def perf(_: dict = Depends(get_current_user)):
        """Performance metrics endpoint"""
        model = get_model()
        fps, inference_fps = get_average_fps()
        return {
            "fps": round(fps, 2),
            "inference_fps": round(inference_fps, 2),
            "active_peer_connections": len(get_peer_connections()),
            "device": get_device_info(),
            "model_loaded": model is not None,
            "cuda_available": torch.cuda.is_available(),
            "cpu_percent": get_cpu_percent(),
            "gpu_percent": get_gpu_percent(),
        }

    @app.get("/api/model-info")
    async def model_info(_: dict = Depends(get_current_user)):
        """Model information endpoint"""
        return get_model_info()

    @app.post("/api/recording/start/{client_id}")
    async def start_recording_endpoint(client_id: str, current_user: dict = Depends(get_current_user)):
        """Start recording for a client"""
        _owned_client(client_id, current_user)
        detection_track = get_detection_track(client_id)
        if not detection_track:
            return {"success": False, "error": "Client not found or not streaming"}

        if is_recording(client_id):
            return {"success": False, "error": "Already recording"}

        try:
            recording_id = await start_recording(client_id, detection_track)
        except NoActiveMissionError:
            return {"success": False, "error": "Tidak ada misi aktif — rekaman tidak dimulai"}
        if recording_id:
            return {
                "success": True,
                "recording_id": recording_id,
                "message": "Recording started"
            }
        else:
            return {"success": False, "error": "Failed to start recording"}

    @app.post("/api/recording/stop/{client_id}")
    async def stop_recording_endpoint(client_id: str, current_user: dict = Depends(get_current_user)):
        """Stop recording for a client"""
        _owned_client(client_id, current_user)
        if not is_recording(client_id):
            return {"success": False, "error": "Not recording"}

        # Stop recording on detection track FIRST (releases writer)
        detection_track = get_detection_track(client_id)
        if detection_track:
            detection_track.stop_recording()

        # Then save metadata to database
        recording_data = await stop_recording(client_id)
        if recording_data:
            return {
                "success": True,
                "recording": recording_data,
                "message": "Recording stopped"
            }
        else:
            return {"success": False, "error": "Failed to stop recording"}

    @app.get("/api/recording/status/{client_id}")
    async def recording_status_endpoint(client_id: str, current_user: dict = Depends(get_current_user)):
        """Get recording status for a client"""
        _owned_client(client_id, current_user)
        recording = is_recording(client_id)
        info = get_recording_info(client_id) if recording else None
        return {
            "recording": recording,
            # Hanya field yang bisa di-JSON-kan (entri aslinya memuat cv2.VideoWriter)
            "info": {
                "recording_id": info["recording_id"],
                "filename": info["filename"],
                "start_time": info["start_time"].isoformat(),
                "session_id": info["session_id"],
            } if info else None,
        }

    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        """WebSocket endpoint for WebRTC signaling"""
        # client_id jadi bagian nama file rekaman → wajib aman untuk nama file
        if not CLIENT_ID_RE.match(client_id):
            logger.warning(f"WS ditolak: client_id tidak valid {client_id!r}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # CORS tidak berlaku untuk WebSocket: tolak halaman dari origin lain
        # yang mencoba memakai cookie login user (cross-site WebSocket hijacking).
        # Client non-browser tanpa header Origin tetap lewat cek cookie di bawah.
        origin = websocket.headers.get("origin")
        if origin and origin.rstrip("/") not in CORS_ORIGINS:
            logger.warning(f"WS client {client_id} ditolak: origin {origin} tidak diizinkan")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Wajib login: browser tidak bisa kirim header Authorization di WebSocket,
        # tapi cookie httpOnly access_token ikut terkirim saat handshake
        token = websocket.cookies.get("access_token")
        db = SessionLocal()
        try:
            if not token:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
            user = get_user_from_token(token, db)
        except HTTPException:
            logger.warning(f"WS client {client_id} ditolak: tidak terautentikasi")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        finally:
            db.close()

        # client_id yang sedang aktif hanya boleh dipakai ulang oleh user yang
        # sama (sambung ulang dari browser yang sama). User lain ditolak agar
        # tidak bisa mematikan/mengambil alih stream & rekaman operator lain.
        existing = client_connections.get(client_id)
        if existing and existing["user"]["id"] != user["id"]:
            logger.warning(f"WS client {client_id} ditolak: sedang dipakai user lain")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        client_connections[client_id] = {"user": user, "ws": websocket}

        await websocket.accept()
        logger.info(f"WS client {client_id} diterima untuk {user['email']}")
        active_connections.add(websocket)
        logger.info(f"WS client {client_id} connected")

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON dari {client_id}: {e}")
                    continue
                if msg.get("type") == "offer":
                    try:
                        await handle_offer(websocket, client_id, msg)
                    except Exception as offer_err:
                        logger.error(f"handle_offer error {client_id}: {offer_err}")
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Stream gagal: {offer_err}"
                            }))
                        except Exception:
                            pass
                elif msg.get("type") == "ice-candidate":
                    # Browser -> server ICE
                    pass
        except WebSocketDisconnect:
            logger.info(f"WS disconnect {client_id}")
        except Exception as e:
            logger.exception(f"WS error {client_id}: {e}")
        finally:
            active_connections.discard(websocket)
            # Kalau koneksi ini sudah digantikan sambungan ulang (client_id sama),
            # jangan bersihkan — stream milik koneksi baru.
            conn = client_connections.get(client_id)
            if conn is not None and conn["ws"] is websocket:
                client_connections.pop(client_id, None)
                await cleanup_pc(client_id)


def get_device_info():
    """Get device info from models module"""
    from models.yolo_detector import get_device_info as _get_device_info
    return _get_device_info()
