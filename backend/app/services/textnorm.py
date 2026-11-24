"""Unicode-aware text normalisation shared by quote grounding, dedupe, fingerprints and comparison.

ASCII-only normalisation (e.g. re.sub(r"[^a-z0-9 ]", "", ...)) deletes every Telugu and
Devanagari character, which would make every Telugu/Hindi quote "unmatched". Here we keep
letters, digits AND combining marks (matras/vowel signs, Unicode categories Mn/Mc), and drop
only punctuation and symbols.
"""
import unicodedata

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu"}
SUPPORTED_LANGUAGES = tuple(LANGUAGE_NAMES)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").casefold()
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat[0] in ("L", "N") or cat in ("Mn", "Mc"):
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def language_code(value: str | None) -> str:
    """Map Whisper/LLM language names or codes to en/hi/te/other."""
    v = (value or "").strip().lower()
    aliases = {"english": "en", "hindi": "hi", "telugu": "te", "en": "en", "hi": "hi", "te": "te"}
    return aliases.get(v, aliases.get(v[:2], "other") if v else "other")


def language_name(code: str | None) -> str:
    return LANGUAGE_NAMES.get(code or "", (code or "Unknown").capitalize())
