"""Step 2a — Speech-to-text with timestamps (Whisper API or local faster-whisper)."""
from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, MediaProcessingError
from app.services import media, metrics

log = logging.getLogger(__name__)


def normalize_segments(raw: list[dict], offset: float = 0.0, start_id: int = 0) -> list[dict]:
    """Clean raw Whisper segments: drop empty text, apply chunk offset, renumber, fix overlaps."""
    out: list[dict] = []
    for seg in raw:
        text = " ".join(str(seg.get("text", "")).split())
        if not text:
            continue
        start = round(float(seg.get("start", 0)) + offset, 2)
        end = round(max(float(seg.get("end", 0)) + offset, start), 2)
        if out and start < out[-1]["end"]:
            start = out[-1]["end"]
            end = max(end, start)
        out.append({"id": start_id + len(out), "start": start, "end": end, "text": text})
    return out


async def _transcribe_openai(audio: Path) -> tuple[list[dict], str | None]:
    from app.services.llm import get_client

    client = get_client()
    s = get_settings()
    segments: list[dict] = []
    language = None
    for chunk_path, offset in await asyncio.to_thread(media.split_audio, audio):
        try:
            with chunk_path.open("rb") as f:
                resp = await client.audio.transcriptions.create(
                    model=s.STT_MODEL, file=f, response_format="verbose_json", timestamp_granularities=["segment"]
                )
        except Exception as e:
            raise ExternalServiceError("Speech recognition service failed") from e
        language = language or getattr(resp, "language", None)
        raw = [
            {"start": seg.start, "end": seg.end, "text": seg.text} if not isinstance(seg, dict) else seg
            for seg in (getattr(resp, "segments", None) or [])
        ]
        segments.extend(normalize_segments(raw, offset=offset, start_id=len(segments)))
        if chunk_path != audio:
            chunk_path.unlink(missing_ok=True)
    return segments, language


@lru_cache
def _local_model():
    from faster_whisper import WhisperModel

    return WhisperModel(get_settings().LOCAL_WHISPER_MODEL, device="auto", compute_type="int8")


def _transcribe_local_sync(audio: Path) -> tuple[list[dict], str | None]:
    try:
        model = _local_model()
    except ImportError as e:
        raise MediaProcessingError("faster-whisper is not installed; set STT_PROVIDER=openai or install it") from e
    seg_iter, info = model.transcribe(str(audio), vad_filter=True, beam_size=5)
    raw = [{"start": s.start, "end": s.end, "text": s.text} for s in seg_iter]
    return normalize_segments(raw), getattr(info, "language", None)


async def transcribe(audio: Path) -> tuple[list[dict], str | None]:
    provider = get_settings().STT_PROVIDER.lower()
    if provider == "local":
        segments, lang = await asyncio.to_thread(_transcribe_local_sync, audio)
    else:
        segments, lang = await _transcribe_openai(audio)
    if not segments:
        raise MediaProcessingError("No speech was detected in this video")
    metrics.track("audio_seconds", segments[-1]["end"])
    if provider != "local":
        metrics.track("stt_minutes", segments[-1]["end"] / 60)
    log.info("Transcribed %d segments (lang=%s)", len(segments), lang)
    return segments, lang
