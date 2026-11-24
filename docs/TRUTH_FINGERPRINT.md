# Truth Fingerprint & Video Comparison

Every analysed video gets a **Truth Fingerprint**: a compact, versioned record of what the video claims and how well the evidence holds up. Two fingerprints can be compared to find shared claims and see whether the videos rest on the same evidence or present conflicting information.

Code: `backend/app/services/fingerprint.py`, `backend/app/services/compare.py`, `backend/app/api/routes/fingerprints.py`, `frontend/src/components/fingerprint/*`, `frontend/src/pages/ComparePage.jsx`.

## 1. What a fingerprint contains

| Field | Meaning |
|---|---|
| `fingerprint_id` | `LTS-XXXX-XXXX-XXXX`, unique and stable for the video (SHA-256 of the video id) |
| `content_hash` | 16-hex hash of every claim's normalised text, verdict, confidence and grounded sources. **Changes whenever results change.** |
| `total_claims` | number of claims extracted |
| `counts` | verified / false / misleading / unverified |
| `truth_score`, `overall_rating` | from the analysis summary |
| `evidence_quality` | grade A–E, score 0–100, and its four components (below) |
| `timestamps` | every claim's original `start`/`end` in the video, with its verdict |
| `claims` | each claim with its sources (URL, domain, stance, credibility) |
| `versions` | verification history (below) |

### Evidence quality
```
score = 100 × (0.35·coverage + 0.25·credibility + 0.20·diversity + 0.20·confidence)

coverage     share of claims with at least one grounded source (supports / refutes / mixed)
credibility  mean credibility weight of those sources (fact-checker 1.0 … general web 0.5)
diversity    mean over claims of min(1, distinct domains / 3)
confidence   mean evidence-based confidence of decided claims
```
| Grade | Score | Label |
|---|---|---|
| A | ≥ 80 | Strong |
| B | ≥ 65 | Good |
| C | ≥ 50 | Moderate |
| D | ≥ 35 | Weak |
| E | < 35 | Very weak |

Evidence quality is separate from the truth score. A video can be **mostly false with grade A evidence**: we're very sure it's wrong. It can also be **mostly verified with grade D**: it looks right, but the evidence is thin.

### Verification history
A new version is appended every time the analysis completes (first run, and every **Retry**). Each version stores its content hash, model, counts, truth score, evidence grade, and **what changed** since the previous version:
- `verdict_changes`: same claim, different verdict (e.g. *Insufficient Evidence → Verified* once new sources were published)
- `added_claims` / `removed_claims`
- `unchanged: true` when nothing moved

Claims are matched across versions by a normalised-text key, then by ≥85% text similarity. The history is kept on retry. It is deleted only when the user deletes the analysis. The last 50 versions are kept.

### The visual glyph
`FingerprintGlyph.jsx` draws a unique emblem:
- **outer ring**: one arc per claim, placed by its timestamp around the circle, coloured by verdict, thicker when confidence is higher
- **inner ridges**: generated from the content hash, so any change in results visibly changes the pattern
- **centre**: the evidence-quality grade

## 2. Comparing two videos

`GET /api/compare?a=<videoId>&b=<videoId>` runs four checks on every pair of matching claims.

### Step 1: Do they make the same claim?
- **Semantic match** (default): cosine similarity of the claim embeddings saved during verification, threshold **≥ 0.82**. This catches rewordings ("visible from the Moon" ↔ "can be seen from lunar orbit").
- **Lexical fallback** (no embeddings, e.g. sample data): `0.6 × keyword Jaccard + 0.4 × sequence similarity`, threshold **≥ 0.55**.
- Greedy one-to-one matching, best pairs first, so each claim pairs with at most one claim in the other video.

### Step 2: Do they say the same thing?
| Verdict A vs B | Relation |
|---|---|
| same verdict | 🟢 **Consistent** |
| verified vs false | 🔴 **Conflicting** |
| one misleading | 🟡 **Partly conflicting** |
| either side Insufficient Evidence | ⚪ **Undetermined** |

**Different figures:** numbers (including `8,849`, `12%`, `3.5`) are extracted from both claims. If both contain numbers and they differ, the pair is flagged, e.g. *8849 vs 8848*.

### Step 3: Do they use the same evidence?
| URL overlap (shared ÷ all sources of the pair) | Evidence relation |
|---|---|
| ≥ 50% | **Same evidence** |
| any shared URL, or ≥ 30% shared domains | **Overlapping evidence** |
| none shared | **Independent evidence** |
| one side has no grounded source | **Evidence missing on one side** |

Domains used only by A and only by B are listed.

### Step 4: Does a source cut both ways?
If **the same URL supports one video's claim and refutes the other's**, the two videos are stating opposite things about the same fact. That's the strongest conflict signal, and the pair is marked **Conflicting** even if the verdict labels alone wouldn't show it.

### Output
- `summary`: shared claims, counts per relation, claims only in A / only in B, average evidence overlap, sources used by both, `has_conflicts`, a one-line headline
- `matches[]`: both claims (text, timestamp, verdict, confidence), similarity and method, relation, figures, evidence overlap with per-source stances, and a plain-English **insight**

**Example** (the two seeded demo videos):
> *3 shared claims, 2 consistent, 1 conflicting. 1 uses different figures.*
> - **Great Wall**: A says *visible from the Moon* (False), B says *cannot be seen* (Verified). The same Wikipedia article refutes A and supports B, so the videos are stating opposite things.
> - **Everest**: both Verified, same source, but different figures (8,849 vs 8,848 m).
> - **10% brain**: both False, same source.

### Finding videos to compare
`GET /api/compare/candidates?video_id=…` ranks your other analysed videos by how many claims they share with this one. The Compare page uses it to sort the "Video B" list.

## 3. UI
- **Analysis page → Truth Fingerprint card**: ID with copy button, glyph, claim counts, evidence-quality breakdown, clickable timestamp chips (seek the player), expandable verification history, and *Compare with another video*.
- **Compare page** (`/compare?a=…&b=…`, also in the sidebar): two pickers, side-by-side fingerprints, headline and relation filters, and one card per matched pair. The ▶ timestamps open the other analysis at that claim (`/analysis/:id?claim=…`), and sources used with opposite stances are highlighted in red.

## 4. API
| Method | Path | Returns |
|---|---|---|
| GET | `/api/analyses/{videoId}/fingerprint` | fingerprint + `versions` (404 until the analysis completes) |
| GET | `/api/fingerprints/{fingerprintId}` | look up your fingerprint by its LTS code |
| GET | `/api/compare?a=&b=` | comparison (422 if a = b, 404 if either isn't yours or isn't complete) |
| GET | `/api/compare/candidates?video_id=&limit=20` | `[{video_id, fingerprint_id, title, total_claims, shared_claims, updated_at}]` |

## 5. Limits
- Matching works best between videos analysed with the same embedding model. Mixed models fall back to lexical matching.
- "Conflicting" compares verdicts on each video's own wording. It doesn't yet run a dedicated contradiction model (NLI). That's a natural next step.
- Candidate ranking compares against your 200 most recent fingerprints. At larger scale, store claim embeddings in a shared vector index.
