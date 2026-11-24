import pytest

from app.core.exceptions import UnsupportedSourceError
from app.services import media


@pytest.mark.parametrize("url,vid", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ?t=10", "dQw4w9WgXcQ"),
    ("https://youtube.com/shorts/abc123XYZ", "abc123XYZ"),
    ("https://m.youtube.com/watch?v=xyz&list=PL1", "xyz"),
    ("https://www.youtube.com/channel/UC123", None),
])
def test_youtube_id(url, vid):
    assert media.youtube_video_id(url) == vid


def test_classify_platform_youtube():
    info = media.classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", resolve_dns=False)
    assert info.source_type == "platform"
    assert info.platform == "youtube"
    assert "youtube-nocookie.com/embed/dQw4w9WgXcQ" in info.embed_url


def test_classify_vimeo_embed():
    info = media.classify_url("https://vimeo.com/76979871", resolve_dns=False)
    assert info.embed_url == "https://player.vimeo.com/video/76979871"


def test_classify_direct_file():
    info = media.classify_url("https://cdn.example.org/media/talk.mp4", resolve_dns=False)
    assert info.source_type == "direct"


@pytest.mark.parametrize("url", [
    "ftp://example.com/video.mp4",
    "https://example.com/article.html",
    "https://www.youtube.com/channel/UC123",
    "javascript:alert(1)",
])
def test_classify_rejects(url):
    with pytest.raises(UnsupportedSourceError):
        media.classify_url(url, resolve_dns=False)


def test_ssrf_guard_blocks_localhost():
    with pytest.raises(UnsupportedSourceError):
        media.classify_url("http://127.0.0.1/secret.mp4")


def test_lookalike_domain_not_allowed():
    with pytest.raises(UnsupportedSourceError):
        media.classify_url("https://notyoutube.com/watch?v=abc", resolve_dns=False)


def test_upload_extension():
    assert media.validate_upload_filename("clip.MP4") == ".mp4"
    with pytest.raises(UnsupportedSourceError):
        media.validate_upload_filename("malware.exe")
