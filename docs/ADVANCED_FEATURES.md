# Advanced Features

## 1. Source Trust Analyser (`services/trust.py`)
Domain reputation is one signal, never the whole answer. Every evidence source gets a trust score from:

| Signal | Weight | How it's judged |
|---|---|---|
| Publisher | 30% | Fact-checker 1.0 · official/academic 0.9 · established news 0.8 · reference 0.7 · unknown 0.5 (unknown, not untrustworthy) |
| Primary source | 15% | Official domain, peer-reviewed host or DOI → 1.0; secondary write-up → 0.4 |
| Author | 10% | Named author/byline in page metadata (meta tags or JSON-LD) |
| Date | 10% | Publication date present; older than 3 years flagged "check it's still current" |
| References | 10% | Outbound links to other sites; DOI/PubMed/official links count as scholarly |
| Corroboration | 25% | How many **other independent domains** take the same position on this claim |
| Transparency | info | Publisher + author + date disclosed (reported, already reflected above) |

With `TRUST_FETCH_METADATA=true`, each cited page is fetched (8s timeout, 600 KB cap, every redirect SSRF-checked) to read author, date and references. Otherwise those signals are "not checked" and scored neutrally. **Evidence weight = trust score × semantic similarity**, so verdicts lean on sources that are both relevant and trustworthy. The UI shows the level and every reason.

## 2. Multilingual verification: Telugu, Hindi, English
- Whisper detects the language and transcribes it in its own script.
- Claim extraction keeps each claim **in the speaker's language** (`text`) and adds a faithful **English translation** (`text_en`) plus a `language` code. The quote check runs on the original script, using Unicode-aware normalisation that keeps vowel signs (matras).
- Evidence search uses the English claim, the English "fact check" query, **and the original-language wording**, so Indian-language sources and fact-checkers are found too.
- Results can be shown in English, Hindi or Telugu (`GET /api/analyses/{id}/translation?lang=te`). Translations are cached. Any translation that changes a number is rejected and the original is shown instead. Verdicts never depend on a translation.
- Optional `EMBEDDING_PROVIDER=local` uses a multilingual Sentence Transformers model, so Telugu/Hindi claims and English evidence share one vector space.
- Users choose their language on the Profile page.

## 3. Context Manipulation Detector (`services/context.py`)
For every claim, the model compares the extracted statement with ±3 transcript segments and the verdict, and flags: **out of context, selective quote, misleading statistic, missing information, incomplete claim, contradicted elsewhere in the video**. Transcript-based flags must quote the surrounding transcript verbatim, and that quote is checked, so ungrounded flags are dropped. Risk: none / low / medium / high. A second pass finds **pairs of claims in the same video that contradict each other** (shown as a red banner with clickable timestamps).

## 4. Media Authenticity Analysis (`services/authenticity.py`)
Separate from fact verification, run on demand from the analysis page.

| Check | Method | Indicator |
|---|---|---|
| Frame timing | ffprobe frame timestamps | gaps > 3 frame intervals, backwards jumps |
| Scene cuts | FFmpeg `scdet` | cut list (info) |
| Audio splices | noise-floor jumps in 50 ms RMS frames | abrupt background change |
| Cut + audio | coincidence within 0.5s | separate recordings joined |
| Digital silence | exact-zero frames inside speech | common in synthetic/edited audio |
| Lip-sync | OpenCV face → mouth-region motion vs speech loudness cross-correlation | weak correspondence or offset ≥ 0.3s |
| Face consistency | detection flicker, face-vs-frame sharpness ratio | possible blending |

Outcome: **Possible manipulation detected** (two or more independent medium indicators) · **No obvious manipulation indicators detected** · **Inconclusive analysis**. Every result lists which checks ran, which didn't and why, and its limitations. It never says "deepfake". `detector_hook()` is the place to add a trained classifier or a commercial API; its score would be shown separately.

Tested on synthetic FFmpeg videos: a clean clip gives no indicators, and a clip built from three joined recordings gives possible manipulation, with both joins located to within 0.15s.

## 5. Evidence Relationship Graph (`services/graph.py`, `pages/GraphPage.jsx`)
React Flow graph laid out in columns: related claims in your other videos → video → claims → sources. Edges: supports (green), refutes (red), mixed (yellow), contradicts (dashed red, animated), same source (dotted), related (dashed blue). Sources are de-duplicated, so one page that supports one claim and refutes another shows both edges. Click any node for details and links.

## 6. Smart Fact-Check Report (`services/report.py`)
`POST /api/reports/generate` → PDF with: video info, Truth Fingerprint (ID, hash, version, evidence grade), summary and verdict counts, claims table with timestamps, per-claim explanation, context flags and evidence (stance, trust level, URL), in-video contradictions, media authenticity (if run), transcript, method and limitations. Reports are stored per user and download with `GET /api/reports/{id}`. Non-English claims appear in English, because ReportLab can't shape Indic scripts; the original stays in the app.

## 7. Quick claim check
The dashboard's "Check a single claim" (`POST /api/verification/check`) runs the same evidence pipeline on typed text, with no video. Results aren't stored.
