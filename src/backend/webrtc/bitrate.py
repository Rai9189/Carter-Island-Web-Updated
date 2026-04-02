import asyncio
import logging
from typing import Optional, Callable
from config import MIN_BITRATE_KBPS_FLOOR, BITRATE_REAPPLY_SEC

logger = logging.getLogger("carter-backend")


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
        # Mapping payload by codec
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


async def set_sender_bitrate(
    sender,
    max_bitrate_bps: int,
    max_fps: int = 30
) -> Optional[Callable[[str], str]]:
    
    try:
        get_params = getattr(sender, "getParameters", None)
        set_params = getattr(sender, "setParameters", None)
        if callable(get_params) and callable(set_params):
            params = get_params()
            if not getattr(params, "encodings", None):
                params.encodings = [{}]  # type: ignore
            enc = params.encodings[0]  # type: ignore
            enc["maxBitrate"] = int(max_bitrate_bps)
            enc["maxFramerate"] = int(max_fps)
            await set_params(params)  # type: ignore
            return None

        return lambda sdp: _insert_bitrate_and_xgoogle(sdp, max_bitrate_bps // 1000, max_fps)
    except Exception as e:
        logger.warning(f"set_sender_bitrate fallback: {e}")
        return lambda sdp: _insert_bitrate_and_xgoogle(sdp, max_bitrate_bps // 1000, max_fps)


async def periodic_reapply_bitrate(
    client_id: str,
    sender,
    bps: int,
    fps: int,
    peer_connections: dict
):
    try:
        while client_id in peer_connections:
            await set_sender_bitrate(sender, bps, fps)
            await asyncio.sleep(BITRATE_REAPPLY_SEC)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"bitrate reapply err: {e}")


def tune_answer_sdp(
    raw_sdp: str,
    kbps: int,
    fps: int,
    prefer: str,
    disable_twcc: bool
) -> str:
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
