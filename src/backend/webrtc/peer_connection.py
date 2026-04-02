import asyncio
import logging
from typing import Dict
from aiortc import RTCPeerConnection, RTCSessionDescription

from config import (
    RTSP_TRANSPORT,
    MAX_BITRATE_KBPS_DEFAULT,
    TARGET_FPS,
    PREFER_CODEC,
    DISABLE_TWCC_REM
)
from video.rtsp_player import make_rtsp_player
from video.detection_track import RtspDetectionTrack
from webrtc.bitrate import set_sender_bitrate, periodic_reapply_bitrate, tune_answer_sdp

logger = logging.getLogger("carter-backend")

# Global state
peer_connections: Dict[str, RTCPeerConnection] = {}
detection_tracks: Dict[str, RtspDetectionTrack] = {}
bitrate_tasks: Dict[str, asyncio.Task] = {}


async def handle_offer(websocket, client_id: str, message: dict):
    # Get preferences from offer
    offer_sdp = message["sdp"]
    pref_codec = (message.get("codec") or PREFER_CODEC).lower()
    max_kbps = int(message.get("maxBitrateKbps") or MAX_BITRATE_KBPS_DEFAULT)
    fps = int(message.get("fps") or TARGET_FPS)

    # Transport RTSP from query params
    qp = websocket.query_params
    transport = (qp.get("transport") or RTSP_TRANSPORT).lower()

    # Cleanup existing connection
    await cleanup_pc(client_id)

    # Create new peer connection
    pc = RTCPeerConnection()
    peer_connections[client_id] = pc

    # Create RTSP source
    player = make_rtsp_player(transport)
    if not player.video:
        raise RuntimeError("RTSP player has no video track")

    # Create detection track
    det_track = RtspDetectionTrack(player.video)
    detection_tracks[client_id] = det_track

    sender = pc.addTrack(det_track)

    @pc.on("connectionstatechange")
    async def _on_state():
        logger.info(f"{client_id} state: {pc.connectionState}")
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await cleanup_pc(client_id)

    # Set remote description
    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))

    # Set bitrate
    sdp_munger = await set_sender_bitrate(sender, max_kbps * 1000, fps)

    # Create answer
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

    # Start periodic bitrate reapply
    task = asyncio.create_task(
        periodic_reapply_bitrate(client_id, sender, max_kbps * 1000, fps, peer_connections)
    )
    bitrate_tasks[client_id] = task

    # Send answer back to client
    import json
    await websocket.send_text(json.dumps({"type": "answer", "sdp": pc.localDescription.sdp}))
    logger.info(
        f"Answer -> {client_id} | codec={pref_codec}, {max_kbps}kbps, fps={fps}, rtsp={transport}, "
        f"twcc_remb_disabled={DISABLE_TWCC_REM}"
    )


async def cleanup_pc(client_id: str):
    # Stop bitrate task
    task = bitrate_tasks.pop(client_id, None)
    if task:
        task.cancel()

    # Stop detection track recording if active
    det_track = detection_tracks.pop(client_id, None)
    if det_track and det_track.recording:
        det_track.stop_recording()

    # Close peer connection
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


def get_peer_connections() -> Dict[str, RTCPeerConnection]:
    return peer_connections


from typing import Optional

def get_detection_track(client_id: str) -> Optional[RtspDetectionTrack]:
    return detection_tracks.get(client_id)


async def cleanup_all():
    pass
    for cid in list(peer_connections.keys()):
        await cleanup_pc(cid)
