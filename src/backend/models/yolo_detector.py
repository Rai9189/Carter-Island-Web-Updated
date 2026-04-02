"""
YOLO Model Loader and Inference
"""
import os
import logging
import torch
import numpy as np
from typing import Optional, List, Tuple
from config import MODEL_PATH

logger = logging.getLogger("carter-backend")

# Global model instance
custom_model = None
device_info = "CPU"


def load_custom_model():
    """Load and initialize YOLO model with GPU support if available"""
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

        if not os.path.exists(MODEL_PATH):
            logger.warning(f"Model not found at {MODEL_PATH}, running passthrough (no detection).")
            custom_model = None
            return

        from ultralytics import YOLO
        custom_model = YOLO(MODEL_PATH)
        if cuda:
            custom_model.to('cuda')

        # Warmup
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


def get_model():
    """Get the loaded YOLO model instance"""
    return custom_model


def get_device_info():
    """Get device information string"""
    return device_info


def run_inference(
    img: np.ndarray,
    conf: float = 0.45,
    iou: float = 0.5,
    max_det: int = 30
) -> List[Tuple[int, int, int, int, float, str]]:
    """
    Run YOLO inference on an image

    Args:
        img: Input image (BGR format)
        conf: Confidence threshold
        iou: IoU threshold for NMS
        max_det: Maximum number of detections

    Returns:
        List of detections: (x1, y1, x2, y2, confidence, class_name)
    """
    if custom_model is None:
        return []

    try:
        res = custom_model(
            img,
            verbose=False,
            conf=conf,
            iou=iou,
            max_det=max_det,
            device='cuda' if torch.cuda.is_available() else 'cpu'
        )

        dets = []
        for r in res:
            if getattr(r, "boxes", None) is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                cls = int(box.cls[0].cpu().numpy())
                name = f"Class_{cls}"
                if hasattr(custom_model, "names") and cls < len(custom_model.names):
                    name = custom_model.names[cls]
                dets.append((int(x1), int(y1), int(x2), int(y2), confidence, name))

        return dets
    except Exception as e:
        logger.warning(f"Inference error: {e}")
        return []


def get_model_info():
    """Get model information for API responses"""
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
