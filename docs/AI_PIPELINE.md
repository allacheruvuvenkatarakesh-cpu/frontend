# AI Implementation

Guiding rule: **an LLM's opinion is never proof.** The model reads, classifies and explains. Evidence decides the verdict, and arithmetic over that evidence decides the confidence.

## 1. Speech-to-text (`services/transcription.py`)
- FFmpeg converts any input to **16 kHz mono MP3 at 48 kbps**. That's what Whisper is trained on, and it keeps 30 minutes under ~11 MB.
- **API mode** (`STT_PROVIDER=openai`): audio is split into ≤10-minute chunks (the API limit is 25 MB). Each chunk is sent with `response_format="verbose_json"` and `timestamp_granularities=["segment"]`, and chunk offsets are added back to the timestamps.
- **Local mode** (`STT_PROVIDER=local`): `faster-whisper` with int8 quantisation and VAD filtering. Nothing leaves the server.
- `normalize_segments` drops empty text, fixes overlapping times and renumbers the segments. These segment ids are the anchor for everything that follows.

## 2. Claim extraction (`services/claims.py`)
- The transcript is split into **windows of ~3,500 characters with a 2-segment overlap**, so a claim that spans a boundary isn't lost.
- Each segment is shown to the model as `[S12 | 63.2-68.9s] text`. The model returns claims with `segment_ids` and a verbatim `original_quote`. **It never produces timestamps itself.** We look them up from the segment ids.
- The prompt asks for decontextualised, single-fact claims (pronouns resolved, nothing added) and excludes opinions, predictions, jokes and calls to action.
- **Grounding check**: if the quote can't be found in the cited segments (exact or ≥75% fuzzy match), the claim is dropped as a hallucination.

## 3. Claim classification
The same call returns `claim_type` (statistical, historical, scientific, health, political, economic, quote, other) and `checkworthiness` (0–1: specific, consequential, verifiable). Unknown types become `other`. Claims are de-duplicated across windows (≥85% similar text, keeping the more check-worthy one). Claims under 0.4 are dropped, and the top `MAX_CLAIMS_PER_VIDEO` are kept in time order.

## 4. Evidence retrieval (`services/search.py`)
- Two queries per claim: the claim itself (finds primary sources) and `fact check <claim>` (finds existing debunks).
- Providers: **Tavily** (returns page content, recommended), **Serper** (Google snippets), **Wikipedia** (no key).
- Results are de-duplicated by URL. Social media and user-generated sites are blocklisted. Each source gets a **credibility weight**: fact-checkers 1.0 · government/intergovernmental/academic/journals 0.9 · established news 0.8 · reference 0.7 · other 0.5. The tiers are a transparent heuristic, editable in one place, and include Indian fact-checkers and institutions.

## 5. Semantic similarity matching (`services/vectorstore.py`)
- Documents are split into **~700-character passages on sentence boundaries with a 1-sentence overlap**.
- The claim and passages are embedded (`text-embedding-3-small` by default) and stored in a per-analysis index: **ChromaDB** (cosine) or a NumPy in-memory index.
- Because the index is shared across the whole video, evidence found for one claim can also support a related claim.
- The top 12 passages are retrieved by cosine similarity. `select_passages` keeps those ≥ `MIN_EVIDENCE_SCORE`, at most 2 per URL (so one page can't dominate), and at most 8 in total.

## 6. AI-powered fact verification (`services/verification.py`)
The model receives the claim and the numbered passages `[E1]…[E8]`, with instructions to **use only those passages**. For each passage it returns:
- `stance`: supports / refutes / mixed / irrelevant
- `quote`: a verbatim sentence from that passage

It also returns a suggested verdict, a plain-language explanation citing `[E#]`, and any missing context.

**Grounding checks:**
- A stance whose quote isn't found in the passage (≥80% fuzzy) is treated as *irrelevant*.
- Citations to passages that don't exist are removed from the explanation.

## 7. Confidence estimation
Each grounded passage contributes `weight = credibility × similarity` to S (supports), R (refutes) or M (mixed), with T = S + R + M.

```
strength   = 1 − e^(−T / 1.2)                          # more, stronger evidence → closer to 1
agreement  = aligned_weight / T                         # verified: S/T · false: R/T · misleading: (M + 2·min(S,R))/T
diversity  = min(1, distinct_domains / 3)
confidence = strength × (0.4 + 0.6·agreement) × (0.6 + 0.4·diversity)   clipped to [0.05, 0.97]
```
The model is **never asked** for a confidence number. Confidence is `null` when the evidence is insufficient. The full breakdown is stored and shown in tooltips, so a judge can see why a number is what it is.

## 8. Final verdict generation
```
if no grounded relevant passage or T < 0.35          → Insufficient Evidence
model says VERIFIED   allowed only if S > R, S ≥ M, R < 0.5·S
model says FALSE      allowed only if R > S, R ≥ M
model says MISLEADING allowed only if M > 0 or (S > 0 and R > 0)
model says INSUFFICIENT                               → respected
if the model's verdict isn't allowed:
    S > 0 and R > 0  → Misleading (sources disagree)
    otherwise        → Insufficient Evidence
    adjusted = true, with the reason appended to the explanation
```
Summary (`services/timeline.py`): the truth score is a confidence-weighted mean (verified 100, misleading 50, false 0) over decided claims only. If fewer than 30% of claims could be decided, no overall rating is given ("Insufficient Evidence") rather than a misleading score.

## Known limits (say these out loud to judges)
- Retrieval is only as good as the search index: very new or local claims often come back *Insufficient Evidence*, which is the intended behaviour.
- Credibility tiers are domain-level heuristics, not article-level quality.
- Sarcasm and speaker attribution in multi-speaker videos are not modelled yet (see *Future enhancements* in PITCH.md).
- Transcription errors on names and numbers can propagate. The original quote is always shown next to the rewritten claim so users can spot this.
