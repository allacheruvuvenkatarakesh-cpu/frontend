"""Media authenticity checks: pure-function tests + end-to-end on synthetic videos made with FFmpeg.
These synthetic files test the detectors only; they say nothing about real-world accuracy."""
import shutil
import subprocess

import numpy as np
import pytest

from app.services import authenticity as au

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def test_timing_gaps_and_backwards_jumps():
    t = np.arange(0, 10, 0.04)
    assert au.check_timing(t, 25) == []
    gappy = np.concatenate([t[:100], t[110:150], t[170:]])
    ind = au.check_timing(gappy, 25)
    assert ind and ind[0].name == "Gaps in frame timing" and ind[0].severity == "medium"
    back = np.concatenate([t[:100], t[90:]])
    assert any(i.name == "Timestamps jump backwards" for i in au.check_timing(back, 25))


def test_audio_breaks_on_noise_floor_change():
    quiet, loud = np.full(100, -50.0), np.full(100, -25.0)
    assert au.audio_breaks(np.concatenate([quiet, quiet])) == []
    br = au.audio_breaks(np.concatenate([quiet, loud, quiet]))
    assert [round(b) for b in br] == [5, 10]
    fade_to_silence = np.concatenate([quiet, np.full(100, -95.0)])
    assert au.audio_breaks(fade_to_silence) == []  # going silent is not a splice


def test_lip_sync_recovers_offset():
    rng = np.random.default_rng(0)
    speech = np.abs(rng.normal(size=200))
    mouth = np.roll(speech, 2)                       # mouth moves 2 samples (0.4s) after audio
    lag, corr = au.lip_sync(mouth, speech)
    assert corr > 0.9 and abs(lag - 0.4) < 1e-9
    assert au.check_av_sync(lag, corr, 0.9)[0].name == "Audio-video offset"
    assert au.check_av_sync(0.0, 0.5, 0.9) == []
    assert au.check_av_sync(0.0, 0.01, 0.9)[0].name == "Weak lip-audio correspondence"
    assert au.check_av_sync(0.4, 0.9, 0.1) == []     # face barely visible: not assessed


def test_decide_requires_two_independent_medium_indicators():
    I = au.Indicator
    cov = {"duration": 30, "audio": True, "video": True}
    assert au.decide([], cov)[0] == "no_obvious_indicators"
    assert au.decide([I("audio", "x", "medium", "")], cov)[0] == "inconclusive"
    assert au.decide([I("audio", "x", "medium", ""), I("audio", "y", "medium", "")], cov)[0] == "inconclusive"
    assert au.decide([I("audio", "x", "medium", ""), I("timing", "y", "medium", "")], cov)[0] == "possible_manipulation"
    assert au.decide([], {"duration": 3, "audio": True, "video": True})[0] == "inconclusive"


def _ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@needs_ffmpeg
def test_end_to_end_clean_vs_spliced(tmp_path):
    clean = tmp_path / "clean.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=size=160x120:rate=25:duration=15", "-f", "lavfi",
        "-i", "anoisesrc=color=pink:amplitude=0.02:duration=15", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(clean))
    parts = []
    for i, (src, noise, amp) in enumerate([("testsrc2", "pink", "0.01"), ("smptebars", "white", "0.3"),
                                           ("testsrc2", "pink", "0.01")]):
        p = tmp_path / f"p{i}.mp4"
        _ff("-f", "lavfi", "-i", f"{src}=size=160x120:rate=25:duration=6", "-f", "lavfi",
            "-i", f"anoisesrc=color={noise}:amplitude={amp}:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(p))
        parts.append(p)
    lst = tmp_path / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    spliced = tmp_path / "spliced.mp4"
    _ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(spliced))

    r_clean = au.analyse_file(clean)
    r_spliced = au.analyse_file(spliced)
    assert r_clean["outcome"] == "no_obvious_indicators"
    assert r_spliced["outcome"] == "possible_manipulation"
    names = {i["name"] for i in r_spliced["indicators"]}
    assert {"Abrupt background-noise changes", "Cuts that coincide with audio breaks"} <= names
    assert r_spliced["limitations"] and r_spliced["detector"]["used"] is False
