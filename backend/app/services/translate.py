"""Translation of results into the user's language (English, Hindi, Telugu).

Rules that keep translation from changing what a claim says:
  * the model is told to translate meaning exactly and keep every number, name, unit and hedge;
  * every number in the source must reappear in the translation, otherwise the translation is
    rejected and the original text is shown instead (flagged, never silently altered);
  * translations are cached per (language, text), so a result is translated once.
Translation is presentation only: verdicts are always decided on the evidence, never on a
translated sentence.
"""
from __future__ import annotations

import hashlib
import logging
import re

from app.db import mongo
from app.db.mongo import utcnow
from app.services.textnorm import LANGUAGE_NAMES

log = logging.getLogger(__name__)

TRANSLATIONS = "translations"
_DIGITS = re.compile(r"\d+(?:[.,]\d+)*")

SYSTEM_PROMPT = """You are a professional translator for a fact-checking service.
Translate each input string into {language}. Rules:
- Translate the meaning exactly. Do not add, remove, soften or strengthen anything.
- Keep every number, date, unit, name and quantity exactly as written (Western digits).
- Keep hedges ("about", "nearly", "according to") and citation markers like [E1] unchanged.
- Use natural, plain {language} that a general audience understands.
Return JSON: {{"translations": [string, ...]}} with exactly one output per input, in the same order."""


def _key(lang: str, text: str) -> str:
    return hashlib.sha256(f"{lang}|{text}".encode()).hexdigest()


def numbers_preserved(source: str, translated: str) -> bool:
    norm = lambda s: sorted(x.replace(",", "") for x in _DIGITS.findall(s))  # noqa: E731
    return norm(source) == norm(translated)


async def translate_texts(texts: list[str], lang: str) -> list[dict]:
    """Returns [{"text": translated_or_original, "translated": bool, "warning": str | None}]."""
    if lang not in LANGUAGE_NAMES:
        raise ValueError(f"Unsupported language '{lang}'")
    db = mongo.get_db()
    out: list[dict | None] = [None] * len(texts)
    missing: list[int] = []
    for i, t in enumerate(texts):
        if not t or not t.strip():
            out[i] = {"text": t, "translated": False, "warning": None}
            continue
        doc = await db[TRANSLATIONS].find_one({"_id": _key(lang, t)})
        if doc:
            out[i] = {"text": doc["text"], "translated": True, "warning": None}
        else:
            missing.append(i)

    if missing:
        from app.services.llm import safe_chat_json

        batch = [texts[i] for i in missing]
        for start in range(0, len(batch), 20):
            chunk, idxs = batch[start:start + 20], missing[start:start + 20]
            raw = await safe_chat_json(SYSTEM_PROMPT.format(language=LANGUAGE_NAMES[lang]),
                                       "Inputs:\n" + "\n".join(f"{n + 1}. {t}" for n, t in enumerate(chunk)),
                                       max_tokens=4000)
            translations = raw.get("translations") if isinstance(raw.get("translations"), list) else []
            for n, i in enumerate(idxs):
                src = texts[i]
                tr = str(translations[n]).strip() if n < len(translations) and translations[n] else ""
                if not tr:
                    out[i] = {"text": src, "translated": False, "warning": "Translation unavailable; showing original."}
                elif not numbers_preserved(src, tr):
                    log.warning("Rejected translation that changed numbers: %r -> %r", src[:80], tr[:80])
                    out[i] = {"text": src, "translated": False,
                              "warning": "Translation altered a number, so the original is shown."}
                else:
                    await db[TRANSLATIONS].replace_one({"_id": _key(lang, src)},
                                                       {"_id": _key(lang, src), "lang": lang, "text": tr,
                                                        "created_at": utcnow()}, upsert=True)
                    out[i] = {"text": tr, "translated": True, "warning": None}
    return [o for o in out]  # type: ignore[misc]


async def translate_analysis(video_id: str, lang: str) -> dict:
    """Translate an analysis's claims, explanations and summary into `lang`."""
    from app.services.fingerprint import gather_claims

    db = mongo.get_db()
    claims = await gather_claims(video_id)
    results = {r["claim_id"]: r async for r in db[mongo.VERIFICATION_RESULTS].find({"video_id": video_id})}
    analysis = await db[mongo.ANALYSIS_HISTORY].find_one({"video_id": video_id})

    texts, slots = [], []
    for c in claims:
        if c.get("language") == lang:
            slots.append((c["id"], "text", {"text": c["text"], "translated": False, "warning": None}))
        else:
            slots.append((c["id"], "text", len(texts)))
            texts.append(c.get("text_en") or c["text"])
        expl = results.get(c["id"], {}).get("explanation", "")
        slots.append((c["id"], "explanation", len(texts)))
        texts.append(expl)
    summary_text = ((analysis or {}).get("summary") or {}).get("overall_explanation", "")
    texts.append(summary_text)

    if lang == "en":
        translated = [{"text": t, "translated": False, "warning": None} for t in texts]
        # English view of non-English claims comes straight from text_en
    else:
        translated = await translate_texts(texts, lang)

    by_claim: dict[str, dict] = {}
    for cid, field_name, ref in slots:
        val = ref if isinstance(ref, dict) else translated[ref]
        by_claim.setdefault(cid, {})[field_name] = val
    return {"lang": lang, "language": LANGUAGE_NAMES[lang], "claims": by_claim, "summary": translated[-1],
            "note": "Machine translation for readability. Verdicts are based on the evidence, not on this translation."}
