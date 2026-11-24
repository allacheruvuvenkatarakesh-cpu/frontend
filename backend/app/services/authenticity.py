"""Media Authenticity Analysis (deepfake / editing indicators). Separate from fact verification.

This module uses SIGNAL CHECKS, not a trained deepfake classifier:

  timing      frame-timestamp gaps and jumps (cuts, dropped or spliced frames)
  scene       hard scene cuts (FFmpeg scdet), and cuts that coincide with audio breaks
  audio       abrupt background-noise changes (possible audio splices) and stretches of
              perfect digital silence (common in synthetic or heavily edited audio)
  av_sync     correlation between mouth-region motion and speech loudness (OpenCV face
              detection); a large offset or no correspondence is an indicator
  face        unstable face detection and face/background sharpness mismatch (blending)

Outcome is always one of:
  possible_manipulation    two or more independent medium indicators
  no_obvious_indicators    the checks ran with enough coverage and found nothing notable
  inconclusive             too short, no face for lip-sync checks, decode problems, or a single
                           indicator: not enough to say either way

It NEVER says a video "is a deepfake". Editing (cuts, music, compression) also triggers
indicators, so every result carries its limitations. A trained detector or a commercial API
can be added behind `detector_hook` later; its score would be reported separately.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

MAX_SECONDS = 300            # analyse at most the first 5 minutes
SAMPLE_FPS = 5               # frames per second sampled for face / lip checks
AUDIO_SR = 16000
FRAME_MS = 50

LIMITATIONS = [
    "These are signal checks, not a trained deepfake classifier. They detect editing and inconsistency "
    "patterns, which ordinary editing (cuts, B-roll, music, re-encoding) can also produce.",
    "High-quality face swaps and voice clones can pass all of these checks.",
    "Lip-sync checks need a clearly visible, mostly frontal face; otherwise they are not assessed.",
    "Heavy compression from social platforms can hide or create artefacts.",
    "Use this as a prompt for closer inspection, never as proof that a video is real or fake.",
]


@dataclass
class Indicator:
    category: str          # timing | scene | audio | av_sync | face
    name: str
    severity: str          # info | low | medium
    detail: str
    times: list[float] = field(default_factory=list)
    reliability: str = "low"

    def as_dict(self):
        return {"category": self.category, "name": self.name, "severity": self.severity, "detail": self.detail,
                "times": [round(t, 2) for t in self.times[:20]], "reliability": self.reliability}


# ------------------------------------------------------------------ helpers
def _bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} is not installed")
    return path


def probe(path: Path) -> dict:
    r = subprocess.run([_bin("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("File could not be read")
    data = json.loads(r.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fps = None
    if v and v.get("avg_frame_rate", "0/0") != "0/0":
        n, d = v["avg_frame_rate"].split("/")
        fps = float(n) / float(d) if float(d) else None
    return {"duration": float(data.get("format", {}).get("duration", 0) or 0), "has_video": bool(v),
            "has_audio": bool(a), "fps": fps, "width": v.get("width") if v else None,
            "height": v.get("height") if v else None, "video_codec": v.get("codec_name") if v else None,
            "audio_codec": a.get("codec_name") if a else None,
            "encoder": data.get("format", {}).get("tags", {}).get("encoder")}


def load_audio(path: Path, seconds: int = MAX_SECONDS) -> np.ndarray:
    r = subprocess.run([_bin("ffmpeg"), "-v", "error", "-t", str(seconds), "-i", str(path), "-vn", "-ac", "1",
                        "-ar", str(AUDIO_SR), "-f", "s16le", "-"], capture_output=True, timeout=300)
    if r.returncode != 0:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def frame_rms_db(audio: np.ndarray, frame_ms: int = FRAME_MS) -> np.ndarray:
    n = int(AUDIO_SR * frame_ms / 1000)
    if len(audio) < n:
        return np.zeros(0)
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return 20 * np.log10(rms + 1e-9)


def frame_times(path: Path, seconds: int = MAX_SECONDS) -> np.ndarray:
    r = subprocess.run([_bin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+{seconds}",
                        "-show_entries", "frame=pts_time,best_effort_timestamp_time", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, timeout=300)
    vals = []
    for line in r.stdout.splitlines():
        for part in line.split(","):
            try:
                vals.append(float(part))
                break
            except ValueError:
                continue
    return np.array(vals)


def scene_cuts(path: Path, seconds: int = MAX_SECONDS, threshold: float = 12.0) -> list[float]:
    r = subprocess.run([_bin("ffmpeg"), "-v", "error", "-t", str(seconds), "-i", str(path), "-an", "-vf",
                        f"scdet=threshold={threshold},metadata=print:file=-", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    out = []
    for line in r.stdout.splitlines():
        if "lavfi.scd.time=" in line:
            try:
                out.append(float(line.split("lavfi.scd.time=")[1].split()[0]))
            except ValueError:
                pass
    return out


# ------------------------------------------------------------------ checks (pure; tested)
def check_timing(times: np.ndarray, fps: float | None) -> list[Indicator]:
    if len(times) < 10:
        return []
    d = np.diff(times)
    med = float(np.median(d[d > 0])) if np.any(d > 0) else (1 / fps if fps else 0.04)
    gaps = [float(times[i + 1]) for i in np.where(d > med * 3)[0] if 0.5 < times[i + 1] < times[-1] - 0.5]
    backwards = [float(times[i + 1]) for i in np.where(d < -med * 0.5)[0]]
    out = []
    if backwards:
        out.append(Indicator("timing", "Timestamps jump backwards", "medium",
                             f"{len(backwards)} point(s) where frame timestamps go backwards, typical of joined clips.",
                             backwards, "moderate"))
    if gaps:
        sev = "medium" if len(gaps) >= 2 else "low"
        out.append(Indicator("timing", "Gaps in frame timing", sev,
                             f"{len(gaps)} gap(s) longer than 3 frame intervals: dropped frames or a splice.",
                             gaps, "moderate"))
    return out


def audio_breaks(db: np.ndarray, frame_ms: int = FRAME_MS, win_s: float = 1.5, jump_db: float = 10.0) -> list[float]:
    """Points where the background noise floor changes abruptly (10th-percentile level in the
    window before vs after), excluding fades into or out of silence."""
    w = int(win_s * 1000 / frame_ms)
    if len(db) < 2 * w + 2:
        return []
    smooth = np.convolve(db, np.ones(4) / 4, mode="same")
    out, last = [], -1e9
    for i in range(w, len(db) - w):
        before, after = np.percentile(db[i - w:i], 10), np.percentile(db[i:i + w], 10)
        if abs(after - before) >= jump_db and min(before, after) > -70:
            # pinpoint: the largest level step inside the surrounding window
            lo, hi = i - w // 2, min(i + w, len(db) - 2)
            j = lo + int(np.argmax(np.abs(np.diff(smooth[lo:hi + 1]))))
            t = (j + 1) * frame_ms / 1000
            if t - last > 2 * win_s:
                out.append(t)
                last = t
    return out


def check_audio(audio: np.ndarray) -> tuple[list[Indicator], list[float]]:
    db = frame_rms_db(audio)
    if len(db) < 40:
        return [], []
    out = []
    breaks = audio_breaks(db)
    if breaks:
        sev = "medium" if len(breaks) >= 2 else "low"
        out.append(Indicator("audio", "Abrupt background-noise changes", sev,
                             f"{len(breaks)} point(s) where the background noise level changes suddenly: possible "
                             "audio splices (also caused by cuts between recordings or added music).", breaks, "moderate"))
    speechy = db > -45
    if speechy.mean() > 0.2:
        n = int(AUDIO_SR * FRAME_MS / 1000)
        frames = audio[: len(audio) // n * n].reshape(-1, n)
        digital_zero = (np.abs(frames).max(axis=1) < 1e-4)
        inside = digital_zero[np.argmax(speechy): len(speechy) - np.argmax(speechy[::-1])]
        frac = float(inside.mean()) if len(inside) else 0.0
        if frac > 0.05:
            out.append(Indicator("audio", "Perfect digital silence between speech", "low",
                                 f"{frac:.0%} of the speech section is exact digital silence. Real microphones always pick "
                                 "up some noise; this pattern is common in synthetic or heavily edited audio.",
                                 [], "low"))
    return out, breaks


def check_cuts_vs_audio(cuts: list[float], breaks: list[float], duration: float) -> list[Indicator]:
    out = []
    if cuts:
        per_min = len(cuts) / max(duration / 60, 0.1)
        out.append(Indicator("scene", "Scene cuts", "info", f"{len(cuts)} hard cut(s) ({per_min:.1f} per minute). "
                             "Normal in edited videos; listed so reviewers can inspect them.", cuts, "moderate"))
    joint = [c for c in cuts if any(abs(c - b) <= 0.5 for b in breaks)]
    if joint:
        out.append(Indicator("scene", "Cuts that coincide with audio breaks", "medium" if len(joint) >= 2 else "low",
                             f"{len(joint)} cut(s) line up with a sudden change in background audio, which suggests "
                             "separate recordings were joined at those points.", joint, "moderate"))
    return out


def lip_sync(mouth_motion: np.ndarray, loudness: np.ndarray, fps: float = SAMPLE_FPS, max_lag_s: float = 1.0):
    """Normalised cross-correlation between mouth motion and speech loudness.
    Returns (best_lag_seconds, peak_correlation) or (None, None) if not enough signal."""
    n = min(len(mouth_motion), len(loudness))
    if n < fps * 8:
        return None, None
    m = mouth_motion[:n] - mouth_motion[:n].mean()
    a = loudness[:n] - loudness[:n].mean()
    if m.std() < 1e-6 or a.std() < 1e-6:
        return None, None
    m, a = m / m.std(), a / a.std()
    best, best_lag = -1.0, 0
    L = int(max_lag_s * fps)
    for lag in range(-L, L + 1):
        x, y = (m[lag:], a[: n - lag]) if lag >= 0 else (m[: n + lag], a[-lag:])
        c = float((x * y).mean())
        if c > best:
            best, best_lag = c, lag
    return best_lag / fps, best


def check_av_sync(lag: float | None, corr: float | None, face_coverage: float) -> list[Indicator]:
    if lag is None or face_coverage < 0.4:
        return []
    if corr < 0.08:
        return [Indicator("av_sync", "Weak lip-audio correspondence", "medium",
                          f"Mouth movement barely tracks the speech (peak correlation {corr:.2f}). Possible dubbing, "
                          "lip-sync manipulation, or a voice-over / off-screen speaker.", [], "low")]
    if abs(lag) >= 0.3:
        return [Indicator("av_sync", "Audio-video offset", "medium",
                          f"Speech appears {abs(lag):.1f}s {'after' if lag > 0 else 'before'} mouth movement "
                          f"(correlation {corr:.2f}). Can be an encoding fault or replaced audio.", [], "moderate")]
    return []


def check_face(found: np.ndarray, sharp_ratio: np.ndarray) -> list[Indicator]:
    out = []
    if len(found) >= 20 and found.mean() >= 0.4:
        flips = int(np.abs(np.diff(found.astype(int))).sum())
        if flips / len(found) > 0.25:
            out.append(Indicator("face", "Unstable face detection", "low",
                                 f"The face is detected and lost {flips} times in {len(found)} samples. Can come from "
                                 "motion or occlusion, and sometimes from face-swap artefacts.", [], "low"))
    r = sharp_ratio[np.isfinite(sharp_ratio)]
    if len(r) >= 10:
        med = float(np.median(r))
        if med < 0.25 or med > 4.0:
            out.append(Indicator("face", "Face sharpness differs from the rest of the frame", "low",
                                 f"The face region is {'much blurrier' if med < 0.25 else 'much sharper'} than the "
                                 f"background (median ratio {med:.2f}), a possible sign of blending or a pasted face.",
                                 [], "low"))
    return out


def decide(indicators: list[Indicator], coverage: dict) -> tuple[str, str]:
    medium_cats = {i.category for i in indicators if i.severity == "medium"}
    if len(medium_cats) >= 2:
        return "possible_manipulation", (f"Medium-severity indicators in {len(medium_cats)} independent checks "
                                         f"({', '.join(sorted(medium_cats))}). Inspect the flagged moments.")
    enough = coverage.get("duration", 0) >= 5 and coverage.get("audio") and coverage.get("video")
    if medium_cats or not enough:
        why = ("one medium indicator alone is not enough to judge" if medium_cats
               else "the checks could not cover enough of the media")
        return "inconclusive", f"Inconclusive: {why}."
    return "no_obvious_indicators", ("No obvious manipulation indicators in the checks that ran. This does not prove "
                                     "the video is authentic.")


# ------------------------------------------------------------------ video sampling (OpenCV)
class FaceModelUnavailable(RuntimeError):
    pass


def sample_faces(path: Path, seconds: int = MAX_SECONDS):
    """Returns (face_found[bool], mouth_motion[float], sharp_ratio[float]) sampled at SAMPLE_FPS."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return np.zeros(0, bool), np.zeros(0), np.zeros(0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(int(round(fps / SAMPLE_FPS)), 1)
    cascade_path = Path(getattr(cv2, "data", None).haarcascades if hasattr(cv2, "data") else "") / \
        "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(str(cascade_path)) if cascade_path.exists() else None
    if cascade is None or cascade.empty():
        cap.release()
        raise FaceModelUnavailable("OpenCV face model not found (install opencv-python-headless 4.x)")
    found, motion, sharp = [], [], []
    prev_mouth = None
    idx, max_idx = 0, int(seconds * fps)
    while idx < max_idx:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            scale = 480 / max(gray.shape[1], 1)
            small = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray
            faces = cascade.detectMultiScale(small, scaleFactor=1.2, minNeighbors=5, minSize=(40, 40))
            if len(faces):
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                found.append(True)
                mouth = cv2.resize(small[y + int(h * 0.65): y + h, x + int(w * 0.25): x + int(w * 0.75)], (48, 24))
                motion.append(float(np.abs(mouth.astype(np.float32) - prev_mouth).mean()) if prev_mouth is not None else 0.0)
                prev_mouth = mouth.astype(np.float32)
                face_var = cv2.Laplacian(small[y:y + h, x:x + w], cv2.CV_64F).var()
                frame_var = cv2.Laplacian(small, cv2.CV_64F).var()
                sharp.append(face_var / frame_var if frame_var > 1e-6 else np.nan)
            else:
                found.append(False)
                motion.append(0.0)
                prev_mouth = None
        idx += 1
    cap.release()
    return np.array(found, bool), np.array(motion), np.array(sharp, dtype=float)


def loudness_track(audio: np.ndarray, fps: float = SAMPLE_FPS) -> np.ndarray:
    n = int(AUDIO_SR / fps)
    if len(audio) < n:
        return np.zeros(0)
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    return np.sqrt((frames ** 2).mean(axis=1))


def detector_hook(path: Path) -> dict | None:
    """Extension point for a trained detector or external API. Returns None (not configured)."""
    return None


# ------------------------------------------------------------------ main
def analyse_file(path: Path) -> dict:
    meta = probe(path)
    indicators: list[Indicator] = []
    checks: dict[str, str] = {}
    audio = load_audio(path) if meta["has_audio"] else np.zeros(0, np.float32)
    breaks: list[float] = []
    if meta["has_audio"] and len(audio):
        a_ind, breaks = check_audio(audio)
        indicators += a_ind
        checks["audio"] = "assessed"
    else:
        checks["audio"] = "not assessed (no audio track)"

    face_cov = 0.0
    if meta["has_video"]:
        times = frame_times(path)
        indicators += check_timing(times, meta["fps"])
        checks["timing"] = "assessed" if len(times) >= 10 else "not assessed (too few frames)"
        cuts = scene_cuts(path)
        indicators += check_cuts_vs_audio(cuts, breaks, min(meta["duration"], MAX_SECONDS))
        checks["scene"] = "assessed"
        try:
            found, motion, sharp = sample_faces(path)
            face_cov = float(found.mean()) if len(found) else 0.0
            indicators += check_face(found, sharp)
            checks["face"] = "assessed" if face_cov >= 0.4 else f"limited (face visible in {face_cov:.0%} of samples)"
            if len(audio) and face_cov >= 0.4:
                lag, corr = lip_sync(motion, loudness_track(audio))
                indicators += check_av_sync(lag, corr, face_cov)
                checks["av_sync"] = "assessed" if lag is not None else "not assessed (not enough speech)"
            else:
                checks["av_sync"] = "not assessed (no clearly visible face)"
        except ImportError:
            checks["face"] = checks["av_sync"] = "not assessed (OpenCV not installed)"
        except FaceModelUnavailable as e:
            checks["face"] = checks["av_sync"] = f"not assessed ({e})"
    else:
        checks.update({"timing": "not assessed (audio only)", "scene": "not assessed (audio only)",
                       "face": "not assessed (audio only)", "av_sync": "not assessed (audio only)"})

    outcome, summary = decide(indicators, {"duration": meta["duration"], "audio": checks["audio"] == "assessed",
                                           "video": meta["has_video"]})
    labels = {"possible_manipulation": "Possible manipulation detected",
              "no_obvious_indicators": "No obvious manipulation indicators detected",
              "inconclusive": "Inconclusive analysis"}
    return {
        "outcome": outcome, "label": labels[outcome], "summary": summary,
        "indicators": [i.as_dict() for i in indicators], "checks": checks,
        "media": {k: meta[k] for k in ("duration", "has_video", "has_audio", "fps", "width", "height",
                                       "video_codec", "audio_codec", "encoder")},
        "analysed_seconds": min(meta["duration"], MAX_SECONDS),
        "detector": detector_hook(path) or {"used": False, "note": "No trained deepfake classifier configured; signal checks only."},
        "limitations": LIMITATIONS,
    }


# ------------------------------------------------------------------ job (MongoDB + file handling)
DEEPFAKE = "deepfake_analysis"


async def run_job(video_id: str) -> None:
    import asyncio

    from app.core.config import get_settings
    from app.db import mongo
    from app.db.mongo import utcnow
    from app.services import media

    db = mongo.get_db()
    video = await db[mongo.VIDEOS].find_one({"_id": video_id})
    tmp: Path | None = None
    try:
        await db[DEEPFAKE].update_one({"video_id": video_id}, {"$set": {"status": "running", "updated_at": utcnow()}})
        if video.get("file_path") and Path(video["file_path"]).exists():
            path = Path(video["file_path"])
        elif video.get("source_type") == "platform":
            # low-resolution copy for frame analysis; deleted afterwards
            tmp_dir = get_settings().STORAGE_DIR / "tmp" / f"auth-{video_id}"
            path = await asyncio.to_thread(media.download_platform_video_lowres, video["source_url"], tmp_dir)
            tmp = path
        else:
            raise RuntimeError("No video file is available for this analysis")
        result = await asyncio.to_thread(analyse_file, path)
        await db[DEEPFAKE].update_one({"video_id": video_id}, {"$set": {
            "status": "completed", "result": result, "error": None, "updated_at": utcnow()}})
    except Exception as e:  # noqa: BLE001
        log.warning("Authenticity analysis failed for %s: %s", video_id, e)
        msg = getattr(e, "message", None) or str(e) or "Analysis failed"
        await db[DEEPFAKE].update_one({"video_id": video_id}, {"$set": {
            "status": "failed", "error": msg, "updated_at": utcnow()}})
    finally:
        if tmp:
            shutil.rmtree(tmp.parent, ignore_errors=True)
