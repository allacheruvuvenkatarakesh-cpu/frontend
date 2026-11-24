"""Smart Fact-Check Report: a downloadable PDF of one analysis.

Sections: video information · Truth Fingerprint · overall summary · claims table ·
claim details (explanation, context flags, evidence with stance + trust level + URL) ·
in-video contradictions · media authenticity (if run) · transcript · method & limitations.

ReportLab cannot shape Indic scripts (Telugu/Devanagari conjuncts would render wrongly), so
the PDF uses each claim's English translation and says so; the original-language text is
always available in the app. English transcripts are included in full.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NAVY = colors.HexColor("#14213D")
MUTED = colors.HexColor("#42629B")
TINT = colors.HexColor("#F1F4F9")
VERDICT = {"verified": ("Verified", "#16A34A"), "false": ("False", "#DC2626"),
           "misleading": ("Misleading", "#B45309"), "unverified": ("Insufficient Evidence", "#6B7280")}
LIMITATIONS = [
    "Verdicts are produced by an AI pipeline from evidence retrieved by web search. They can be wrong; read the cited sources.",
    "'Insufficient Evidence' means the retrieved sources did not settle the claim. It does not mean the claim is false.",
    "Confidence is computed from the amount, agreement, independence and trustworthiness of the evidence, not from the model's own certainty.",
    "Source trust scores combine several signals (publisher, primary source, author, date, references, corroboration); none is decisive alone.",
    "Speech recognition can mishear names and numbers. Each claim lists the words actually spoken; check them at the timestamp.",
    "Media authenticity results are signal checks, not proof that a video is real or fake.",
]


def _fmt_time(s: float | None) -> str:
    if s is None:
        return "--:--"
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _p(text, style):
    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


def build_pdf(path: Path, *, video: dict, analysis: dict, transcript: dict | None, claims: list[dict],
              fingerprint: dict | None, authenticity: dict | None, generated_by: str) -> Path:
    ss = getSampleStyleSheet()
    st = {
        "title": ParagraphStyle("t", parent=ss["Title"], textColor=NAVY, fontSize=22, alignment=TA_LEFT, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=ss["Normal"], textColor=MUTED, fontSize=10, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], textColor=NAVY, fontSize=14, spaceBefore=12, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=ss["Heading3"], textColor=NAVY, fontSize=11, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=13),
        "small": ParagraphStyle("sm", parent=ss["Normal"], fontSize=8, leading=10.5, textColor=colors.HexColor("#334155")),
        "cell": ParagraphStyle("c", parent=ss["Normal"], fontSize=8.5, leading=11),
    }
    grid = TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                       ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                       ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C4D1E5")),
                       ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TINT])])
    kv = TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])
    now = datetime.now(timezone.utc)
    summary = analysis.get("summary") or {}
    story = [_p("LiveTruth Shield: Fact-Check Report", st["title"]),
             _p(f"Generated {now:%d %b %Y %H:%M} UTC for {generated_by}", st["sub"])]

    # video
    story.append(_p("Video", st["h2"]))
    lang = (transcript or {}).get("language") or "unknown"
    rows = [["Title", video.get("title")], ["Source", video.get("source_url") or "Uploaded file"],
            ["Platform", (video.get("platform") or video.get("source_type") or "").capitalize()],
            ["Duration", _fmt_time(video.get("duration"))], ["Spoken language", lang],
            ["Analysed", (analysis.get("completed_at") or analysis.get("updated_at") or now).strftime("%d %b %Y %H:%M UTC")]]
    story.append(Table([[r[0], _p(r[1], st["body"])] for r in rows], colWidths=[35 * mm, 135 * mm], style=kv))

    # fingerprint
    if fingerprint:
        cur, versions = fingerprint["current"], fingerprint.get("versions", [])
        eq = cur["evidence_quality"]
        story.append(_p("Truth Fingerprint", st["h2"]))
        story.append(Table([[k, _p(v, st["body"])] for k, v in [
            ["Fingerprint ID", cur["fingerprint_id"]], ["Content hash", cur["content_hash"]],
            ["Version", f"v{versions[-1]['version'] if versions else 1} of {len(versions) or 1}"],
            ["Evidence quality", f"Grade {eq['grade']} ({eq['label']}), {eq['score']:.0f}/100: coverage {eq['coverage']:.0%}, "
                                 f"source trust {eq['avg_credibility']:.2f}, diversity {eq['source_diversity']:.2f}"],
        ]], colWidths=[35 * mm, 135 * mm], style=kv))

    # summary
    counts = summary.get("counts", {})
    story.append(_p("Summary", st["h2"]))
    score = f" · truth score {summary['truth_score']:.0f}/100" if summary.get("truth_score") is not None else ""
    story.append(Paragraph(f"<b>{escape(summary.get('overall_rating', 'Pending'))}</b>{score}", st["body"]))
    story.append(_p(summary.get("overall_explanation", ""), st["body"]))
    story.append(Spacer(1, 4))
    story.append(Table([["Claims", "Verified", "False", "Misleading", "Insufficient evidence"],
                        [summary.get("total_claims", len(claims)), counts.get("verified", 0), counts.get("false", 0),
                         counts.get("misleading", 0), counts.get("unverified", 0)]],
                       colWidths=[34 * mm] * 5, style=grid))

    # claims table
    if claims:
        story.append(_p("Claims", st["h2"]))
        data = [["ID", "Time", "Verdict", "Conf.", "Claim"]]
        for c in claims:
            label, col = VERDICT.get(c.get("verdict") or "unverified", VERDICT["unverified"])
            data.append([c.get("code") or "", _fmt_time(c["start"]),
                         Paragraph(f'<font color="{col}"><b>{label}</b></font>', st["cell"]),
                         "—" if c.get("confidence") is None else f"{c['confidence']:.0%}",
                         _p(c.get("text_en") or c["text"], st["cell"])])
        story.append(Table(data, colWidths=[15 * mm, 14 * mm, 30 * mm, 13 * mm, 98 * mm], style=grid, repeatRows=1))
        if any(c.get("language") not in (None, "en") for c in claims):
            story.append(_p("Non-English claims are shown in English translation in this PDF; the original wording is in the app.",
                            st["small"]))

        story.append(PageBreak())
        story.append(_p("Claim details and evidence", st["h2"]))
        for c in claims:
            label, col = VERDICT.get(c.get("verdict") or "unverified", VERDICT["unverified"])
            block = [Paragraph(f'<b>{escape(c.get("code") or "")}</b> · {_fmt_time(c["start"])} · '
                               f'<font color="{col}"><b>{label}</b></font>', st["h3"]),
                     _p(c.get("text_en") or c["text"], st["body"])]
            if c.get("original_quote"):
                block.append(_p(f"Spoken words: “{c['original_quote']}”" if c.get("language") in (None, "en")
                                else "Spoken words: see the app (original script)", st["small"]))
            if c.get("explanation"):
                block.append(_p(f"Why: {c['explanation']}", st["body"]))
            ctx = c.get("context_analysis") or {}
            for f in ctx.get("flags", []):
                block.append(_p(f"Context flag: {f['label']}: {f['explanation']}", st["small"]))
            ev = [e for e in c.get("evidence", []) if e.get("stance") != "irrelevant"]
            if ev:
                rows = [["#", "Stance", "Trust", "Source"]]
                for i, e in enumerate(ev, start=1):
                    trust = (e.get("trust") or {}).get("level") or "—"
                    rows.append([str(i), e["stance"].capitalize(), trust,
                                 Paragraph(f'{escape(e.get("source_name") or "")}: {escape(e.get("title") or "")}<br/>'
                                           f'<font color="#324D80">{escape(e["url"])}</font>', st["cell"])])
                block.append(Table(rows, colWidths=[8 * mm, 20 * mm, 16 * mm, 126 * mm], style=grid))
            else:
                block.append(_p("No source directly addressed this claim.", st["small"]))
            block.append(Spacer(1, 6))
            story.append(KeepTogether(block[:3]))
            story.extend(block[3:])

    # contradictions
    contra = ((analysis.get("context_summary") or {}).get("contradictions")) or []
    if contra:
        story.append(_p("Contradictions within the video", st["h2"]))
        for x in contra:
            story.append(_p(f"{x['a']} ({_fmt_time(x.get('start_a'))}) vs {x['b']} ({_fmt_time(x.get('start_b'))}): "
                            f"{x.get('explanation', '')}", st["body"]))

    # authenticity
    if authenticity and authenticity.get("result"):
        r = authenticity["result"]
        story.append(_p("Media authenticity (separate from fact verification)", st["h2"]))
        story.append(Paragraph(f"<b>{escape(r['label'])}</b>: {escape(r['summary'])}", st["body"]))
        for i in r.get("indicators", []):
            story.append(_p(f"[{i['severity']}] {i['name']}: {i['detail']}", st["small"]))

    # transcript
    if transcript and transcript.get("segments"):
        story.append(PageBreak())
        story.append(_p("Transcript", st["h2"]))
        if (transcript.get("language") or "en")[:2] == "en":
            rows = [[_fmt_time(s["start"]), _p(s["text"], st["cell"])] for s in transcript["segments"]]
            story.append(Table(rows, colWidths=[16 * mm, 154 * mm],
                               style=TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                                 ("TEXTCOLOR", (0, 0), (0, -1), MUTED)])))
        else:
            story.append(_p(f"The transcript is in {transcript.get('language')} and is available in the app. "
                            "The PDF engine can't render that script reliably.", st["body"]))

    story.append(_p("Method and limitations", st["h2"]))
    for line in LIMITATIONS:
        story.append(_p(f"• {line}", st["small"]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        fid = (fingerprint or {}).get("current", {}).get("fingerprint_id", "")
        canvas.drawString(18 * mm, 10 * mm, f"LiveTruth Shield · {fid}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=f"Fact-check report: {video.get('title', '')}",
                            author="LiveTruth Shield")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path
