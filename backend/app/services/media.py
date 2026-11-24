"""Step 1 — Video capture: URL validation, download, upload handling and audio extraction.

Platform downloads use yt-dlp without cookies or login, so only publicly accessible
videos are captured. Private, age-gated, geo-blocked, members-only and DRM-protected
content is rejected with a clear message rather than worked around.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import math
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.core.config import get_settings
from app.core.exceptions import MediaProcessingError, UnsupportedSourceError

log = logging.getLogger(__name__)

DIRECT_MEDIA_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".m4v", ".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac"}
UPLOAD_EXTENSIONS = DIRECT_MEDIA_EXTENSIONS | {".avi", ".3gp"}

# Whisper API rejects files above 25 MB; we split well below that.
API_CHUNK_SECONDS = 600


@dataclass
class SourceInfo:
    source_type: str          # "platform" | "direct"
    platform: str | None      # e.g. "youtube"
    normalized_url: str
    embed_url: str | None = None


# ---------------------------------------------------------------- URL validation
def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _platform_name(domain: str) -> str:
    return {"youtu.be": "youtube", "x.com": "x", "twitter.com": "x"}.get(domain, domain.split(".")[0])


def youtube_video_id(url: str) -> str | None:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if _host_matches(host, "youtu.be"):
        vid = p.path.lstrip("/").split("/")[0]
        return vid or None
    if _host_matches(host, "youtube.com"):
        if p.path == "/watch":
            return (parse_qs(p.query).get("v") or [None])[0]
        for prefix in ("/shorts/", "/embed/", "/live/"):
            if p.path.startswith(prefix):
                return p.path[len(prefix):].split("/")[0] or None
    return None


def embed_url_for(url: str, platform: str | None) -> str | None:
    if platform == "youtube":
        vid = youtube_video_id(url)
        return f"https://www.youtube-nocookie.com/embed/{vid}?enablejsapi=1" if vid else None
    if platform == "vimeo":
        parts = [x for x in urlparse(url).path.split("/") if x.isdigit()]
        return f"https://player.vimeo.com/video/{parts[0]}" if parts else None
    return None


def assert_public_host(host: str) -> None:
    """SSRF guard for direct media links: refuse hosts that resolve to private networks."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsupportedSourceError(f"Could not resolve host '{host}'") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise UnsupportedSourceError("This URL points to a private or local network address and cannot be used")


def classify_url(url: str, *, resolve_dns: bool = True) -> SourceInfo:
    """Decide how a URL can be captured, or raise UnsupportedSourceError."""
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https") or not p.hostname:
        raise UnsupportedSourceError("Only http(s) links are supported")
    host = p.hostname.lower()

    for domain in get_settings().allowed_platforms:
        if _host_matches(host, domain):
            platform = _platform_name(domain)
            if platform == "youtube" and not youtube_video_id(url):
                raise UnsupportedSourceError("That YouTube link does not point to a single video")
            return SourceInfo("platform", platform, url.strip(), embed_url_for(url, platform))

    ext = Path(p.path).suffix.lower()
    if ext in DIRECT_MEDIA_EXTENSIONS:
        if resolve_dns:
            assert_public_host(host)
        return SourceInfo("direct", None, url.strip())

    allowed = ", ".join(get_settings().allowed_platforms)
    raise UnsupportedSourceError(
        f"Unsupported link. Use a public video from: {allowed}, a direct media file link "
        f"({', '.join(sorted(DIRECT_MEDIA_EXTENSIONS))}), or upload the file."
    )


def validate_upload_filename(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in UPLOAD_EXTENSIONS:
        raise UnsupportedSourceError(f"Unsupported file type '{ext or 'unknown'}'. Allowed: {', '.join(sorted(UPLOAD_EXTENSIONS))}")
    return ext


# ---------------------------------------------------------------- ffmpeg helpers
def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaProcessingError(f"'{name}' is not installed on the server")
    return path


def probe_duration(path: Path) -> float | None:
    ffprobe = _require_binary("ffprobe")
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise MediaProcessingError("The file could not be read as audio or video")
    try:
        return float(json.loads(proc.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def has_audio_stream(path: Path) -> bool:
    ffprobe = _require_binary("ffprobe")
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def extract_audio(src: Path, dest: Path) -> Path:
    """Convert any media to 16 kHz mono MP3 (speech-optimised, small enough for the Whisper API)."""
    ffmpeg = _require_binary("ffmpeg")
    if not has_audio_stream(src):
        raise MediaProcessingError("This video has no audio track, so there is no speech to analyse")
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", str(dest)],
        capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode != 0 or not dest.exists():
        log.error("ffmpeg failed: %s", proc.stderr[-2000:])
        raise MediaProcessingError("Audio extraction failed")
    return dest


def split_audio(src: Path, chunk_seconds: int = API_CHUNK_SECONDS) -> list[tuple[Path, float]]:
    """Split audio into chunks; returns (path, offset_seconds) pairs."""
    duration = probe_duration(src) or 0
    if duration <= chunk_seconds:
        return [(src, 0.0)]
    ffmpeg = _require_binary("ffmpeg")
    chunks = []
    for i in range(math.ceil(duration / chunk_seconds)):
        offset = i * chunk_seconds
        out = src.with_name(f"{src.stem}_part{i:03d}.mp3")
        proc = subprocess.run(
            [ffmpeg, "-y", "-ss", str(offset), "-t", str(chunk_seconds), "-i", str(src), "-c", "copy", str(out)],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            raise MediaProcessingError("Audio splitting failed")
        chunks.append((out, float(offset)))
    return chunks


# ---------------------------------------------------------------- downloads
_YTDLP_ERROR_HINTS = [
    ("private", "This video is private."),
    ("sign in", "This video requires signing in (age-restricted or members-only), so it can't be analysed."),
    ("login", "This video requires signing in, so it can't be analysed."),
    ("not available in your country", "This video is geo-restricted."),
    ("drm", "This video is DRM-protected and can't be captured."),
    ("unavailable", "This video is unavailable."),
    ("live event will begin", "This live stream hasn't started yet."),
]


def download_platform_audio(url: str, dest_dir: Path) -> tuple[Path, dict]:
    """Download the best audio-only stream of a public platform video with yt-dlp."""
    try:
        import yt_dlp
    except ImportError as e:  # pragma: no cover
        raise MediaProcessingError("yt-dlp is not installed on the server") from e

    s = get_settings()
    dest_dir.mkdir(parents=True, exist_ok=True)
    base_opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30}

    try:
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # yt_dlp raises DownloadError/ExtractorError
        raise UnsupportedSourceError(_friendly_ytdlp_error(str(e))) from e

    if info.get("is_live"):
        raise UnsupportedSourceError("Live streams in progress aren't supported yet. Try again once the stream has ended.")
    duration = info.get("duration") or 0
    if duration and duration > s.MAX_VIDEO_MINUTES * 60:
        raise UnsupportedSourceError(f"Video is longer than the {s.MAX_VIDEO_MINUTES}-minute limit")

    opts = {
        **base_opts,
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "max_filesize": s.MAX_UPLOAD_MB * 1024 * 1024,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(result))
    except Exception as e:
        raise UnsupportedSourceError(_friendly_ytdlp_error(str(e))) from e
    if not path.exists():
        raise MediaProcessingError("Download finished but no file was produced")
    meta = {
        "title": info.get("title"),
        "duration": duration or None,
        "uploader": info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "thumbnail": info.get("thumbnail"),
    }
    return path, meta


def _friendly_ytdlp_error(raw: str) -> str:
    low = raw.lower()
    for needle, msg in _YTDLP_ERROR_HINTS:
        if needle in low:
            return msg
    return "Could not access this video. Make sure it is public and the link is correct."


async def download_direct(url: str, dest: Path) -> Path:
    """Stream a direct media link to disk with a size cap."""
    import httpx

    limit = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=60) as client:
            async with client.stream("GET", url) as r:
                if r.status_code != 200:
                    raise UnsupportedSourceError(f"The media link returned HTTP {r.status_code}")
                with dest.open("wb") as f:
                    async for chunk in r.aiter_bytes(1024 * 256):
                        written += len(chunk)
                        if written > limit:
                            raise UnsupportedSourceError(f"File exceeds the {get_settings().MAX_UPLOAD_MB} MB limit")
                        f.write(chunk)
    except httpx.HTTPError as e:
        dest.unlink(missing_ok=True)
        raise UnsupportedSourceError("Could not download the media file") from e
    except UnsupportedSourceError:
        dest.unlink(missing_ok=True)
        raise
    return dest


def download_platform_video_lowres(url: str, dest_dir: Path) -> Path:
    """Low-resolution (≤480p) copy of a public platform video, used only for the media
    authenticity checks and deleted afterwards. Same rules as audio capture: no cookies,
    logins or DRM circumvention."""
    try:
        import yt_dlp
    except ImportError as e:  # pragma: no cover
        raise MediaProcessingError("yt-dlp is not installed on the server") from e
    s = get_settings()
    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30,
            "format": "best[height<=480][ext=mp4]/best[height<=480]/worst",
            "outtmpl": str(dest_dir / "%(id)s.%(ext)s"), "max_filesize": s.MAX_UPLOAD_MB * 1024 * 1024}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
    except Exception as e:
        raise UnsupportedSourceError(_friendly_ytdlp_error(str(e))) from e
    if not path.exists():
        raise MediaProcessingError("Download finished but no file was produced")
    return path
