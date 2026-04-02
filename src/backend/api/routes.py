"""
FastAPI routes for Carter Island Backend
"""
import json
import os
import torch
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from typing import Set

from models.yolo_detector import get_model, get_model_info
from video.detection_track import get_fps, get_inference_fps
from video.recording import start_recording, stop_recording, is_recording, get_recording_info
from webrtc.peer_connection import (
    handle_offer,
    cleanup_pc,
    get_peer_connections,
    get_detection_track
)
from config import RTSP_URL

logger = logging.getLogger("carter-backend")

# Active WebSocket connections
active_connections: Set[WebSocket] = set()


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
            "rtsp_url": RTSP_URL,
        }

    @app.get("/api/health")
    async def health():
        """Health check endpoint with GPU info"""
        gpu = {}
        if torch.cuda.is_available():
            gpu = {
                "gpu_name": torch.cuda.get_device_name(0),
                "mem_total": torch.cuda.get_device_properties(0).total_memory,
                "mem_alloc": torch.cuda.memory_allocated(0),
                "mem_reserved": torch.cuda.memory_reserved(0),
            }

        return {
            "status": "healthy",
            "device": get_device_info(),
            "model_info": get_model_info(),
            "fps": get_fps(),
            "inference_fps": get_inference_fps(),
            "active_peer_connections": len(get_peer_connections()),
            "cuda": torch.cuda.is_available(),
            "torch": torch.__version__,
            "gpu": gpu,
        }

    @app.get("/api/performance")
    async def perf():
        """Performance metrics endpoint"""
        model = get_model()
        return {
            "fps": round(get_fps(), 2),
            "inference_fps": round(get_inference_fps(), 2),
            "active_peer_connections": len(get_peer_connections()),
            "device": get_device_info(),
            "model_loaded": model is not None,
            "cuda_available": torch.cuda.is_available(),
        }

    @app.get("/api/model-info")
    async def model_info():
        """Model information endpoint"""
        return get_model_info()

    @app.post("/api/recording/start/{client_id}")
    async def start_recording_endpoint(client_id: str):
        """Start recording for a client"""
        detection_track = get_detection_track(client_id)
        if not detection_track:
            return {"success": False, "error": "Client not found or not streaming"}

        if is_recording(client_id):
            return {"success": False, "error": "Already recording"}

        recording_id = await start_recording(client_id, detection_track)
        if recording_id:
            return {
                "success": True,
                "recording_id": recording_id,
                "message": "Recording started"
            }
        else:
            return {"success": False, "error": "Failed to start recording"}

    @app.post("/api/recording/stop/{client_id}")
    async def stop_recording_endpoint(client_id: str):
        """Stop recording for a client"""
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
    async def recording_status_endpoint(client_id: str):
        """Get recording status for a client"""
        recording = is_recording(client_id)
        info = get_recording_info(client_id) if recording else None
        return {
            "recording": recording,
            "info": info
        }

    @app.get("/api/video/stream/{filename}")
    async def stream_video(filename: str):
        """Stream video file for playback"""
        from config import RECORDINGS_DIR

        # Security: prevent directory traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        filepath = os.path.join(RECORDINGS_DIR, filename)

        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="Video not found")

        # Detect media type based on file extension
        media_type = "video/webm" if filename.endswith(".webm") else "video/mp4"

        # Return video file with proper content type
        return FileResponse(
            filepath,
            media_type=media_type,
            filename=filename
        )

    @app.get("/api/video/download/{filename}")
    async def download_video(filename: str):
        """Download video file"""
        from config import RECORDINGS_DIR

        # Security: prevent directory traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        filepath = os.path.join(RECORDINGS_DIR, filename)

        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="Video not found")

        # Detect media type based on file extension
        media_type = "video/webm" if filename.endswith(".webm") else "video/mp4"

        # Force download with proper headers
        return FileResponse(
            filepath,
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        """WebSocket endpoint for WebRTC signaling"""
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
                    # Browser -> server ICE
                    pass
        except WebSocketDisconnect:
            logger.info(f"WS disconnect {client_id}")
        except Exception as e:
            logger.exception(f"WS error {client_id}: {e}")
        finally:
            active_connections.discard(websocket)
            await cleanup_pc(client_id)


def get_device_info():
    """Get device info from models module"""
    from models.yolo_detector import get_device_info as _get_device_info
    return _get_device_info()
