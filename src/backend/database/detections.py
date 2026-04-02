"""
Database operations for fish detections
"""
import logging
import httpx
from typing import List, Tuple, Optional
from datetime import datetime
from config import (
    SAVE_DETECTIONS_ENABLED,
    API_BASE_URL,
    MIN_DETECTIONS_TO_SAVE,
    streaming_session_id
)

logger = logging.getLogger("carter-backend")

# HTTP client for API calls
http_client: Optional[httpx.AsyncClient] = None


async def initialize_http_client():
    """Initialize HTTP client for database operations"""
    global http_client
    if SAVE_DETECTIONS_ENABLED:
        http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        logger.info(f"Database saving enabled - Session ID: {streaming_session_id}")
        logger.info(f"API endpoint: {API_BASE_URL}/api/detections")


async def close_http_client():
    """Close HTTP client"""
    global http_client
    if http_client:
        await http_client.aclose()
        http_client = None


async def save_detections_to_db(
    detections: List[Tuple[int, int, int, int, float, str]],
    frame_number: Optional[int] = None
) -> bool:
    """
    Save fish detections to database via Next.js API

    Args:
        detections: List of (x1, y1, x2, y2, confidence, class_name)
        frame_number: Frame number (optional)

    Returns:
        bool: True if successful, False otherwise
    """
    if not SAVE_DETECTIONS_ENABLED or not http_client:
        return False

    if len(detections) < MIN_DETECTIONS_TO_SAVE:
        return False

    try:
        # Format data for API
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

        # Send to API
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
