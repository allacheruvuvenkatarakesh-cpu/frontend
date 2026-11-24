"""Video submission (URL or upload) and authenticated media streaming."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import analysis_limiter, get_current_user
from app.api.serializers import video_out
from app.core.config import get_settings
from app.core.exceptions import AuthError, NotFoundError, UnsupportedSourceError
from app.core.security import create_media_token, decode_token
from app.db import mongo
from app.db.mongo import new_id, utcnow
from app.models.schemas import AnalysisStatus, MediaTokenOut, VideoFromUrl, VideoOut
from app.services import media, pipeline

router = APIRouter(prefix="/videos", tags=["videos"])


async def _create(user: dict, video: dict) -> VideoOut:
    db = mongo.get_db()
    await db[mongo.VIDEOS].insert_one(video)
    now = utcnow()
    await db[mongo.ANALYSIS_HISTORY].insert_one({
        "_id": new_id(), "video_id": video["_id"], "user_id": user["_id"], "status": AnalysisStatus.QUEUED.value,
        "stage_label": pipeline.STAGE_LABELS[AnalysisStatus.QUEUED], "progress": 0, "error": None,
        "summary": None, "timeline": [], "created_at": now, "updated_at": now,
    })
    pipeline.schedule_analysis(video["_id"])
    return video_out(video)


@router.post("/url", response_model=VideoOut, status_code=202)
async def submit_url(body: VideoFromUrl, user: dict = Depends(get_current_user)):
    analysis_limiter.check(user["_id"])
    info = media.classify_url(str(body.url))
    default_title = f"{(info.platform or 'Video').capitalize()} video"
    video = {
        "_id": new_id(), "user_id": user["_id"], "title": body.title or default_title,
        "title_is_default": not body.title, "source_type": info.source_type, "source_url": info.normalized_url,
        "platform": info.platform, "embed_url": info.embed_url, "file_path": None,
        "playable": False, "duration": None, "created_at": utcnow(),
    }
    return await _create(user, video)


@router.post("/upload", response_model=VideoOut, status_code=202)
async def upload(file: UploadFile = File(...), title: str | None = Form(default=None),
                 user: dict = Depends(get_current_user)):
    analysis_limiter.check(user["_id"])
    s = get_settings()
    ext = media.validate_upload_filename(file.filename or "")
    vid = new_id()
    dest = s.STORAGE_DIR / "videos" / f"{vid}{ext}"
    limit = s.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        with dest.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise UnsupportedSourceError(f"File exceeds the {s.MAX_UPLOAD_MB} MB limit")
                f.write(chunk)
    except UnsupportedSourceError:
        dest.unlink(missing_ok=True)
        raise
    if written == 0:
        dest.unlink(missing_ok=True)
        raise UnsupportedSourceError("The uploaded file is empty")

    video = {
        "_id": vid, "user_id": user["_id"], "title": (title or Path(file.filename).stem)[:200],
        "title_is_default": False, "source_type": "upload", "source_url": None, "platform": None,
        "embed_url": None, "file_path": str(dest), "original_filename": file.filename, "size_bytes": written,
        "playable": True, "duration": None, "created_at": utcnow(),
    }
    return await _create(user, video)


@router.get("/{video_id}/media-token", response_model=MediaTokenOut)
async def media_token(video_id: str, user: dict = Depends(get_current_user)):
    video = await mongo.get_db()[mongo.VIDEOS].find_one({"_id": video_id, "user_id": user["_id"]})
    if not video or not video.get("playable"):
        raise NotFoundError("No playable file for this video")
    token = create_media_token(user["_id"], video_id)
    return MediaTokenOut(token=token, stream_url=f"/api/videos/{video_id}/stream?token={token}")


@router.get("/{video_id}/stream")
async def stream(video_id: str, token: str):
    """Range-capable file streaming (Starlette's FileResponse handles Range headers)."""
    data = decode_token(token, "media")
    if data.get("vid") != video_id:
        raise AuthError("Token does not match this video")
    video = await mongo.get_db()[mongo.VIDEOS].find_one({"_id": video_id, "user_id": data["sub"]})
    if not video or not video.get("file_path") or not Path(video["file_path"]).exists():
        raise NotFoundError("Video file not found")
    return FileResponse(video["file_path"], headers={"Cache-Control": "private, max-age=3600"})
