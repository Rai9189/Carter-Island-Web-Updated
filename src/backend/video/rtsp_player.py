"""
RTSP Player utilities
"""
import logging
from aiortc.contrib.media import MediaPlayer
from config import RTSP_URL

logger = logging.getLogger("carter-backend")


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
