# API Reference

Base URL: `/api` · Interactive docs at `/docs` (Swagger) and `/redoc`.
Auth: `Authorization: Bearer <access_token>` on every endpoint except health, register, login, and stream (which uses `?token=`).

**Error format (all errors):**
```json
{ "error": { "code": "unsupported_source", "message": "Unsupported link. …", "details": {} } }
```
Codes: `validation_error` 422 · `unsupported_source` 422 · `media_processing_failed` 422 · `unauthorized` 401 · `forbidden` 403 · `not_found` 404 · `conflict` 409 · `rate_limited` 429 · `external_service_error` 502 · `service_not_configured` 503 · `internal_error` 500.

---

## Health
### `GET /health`
```json
{ "status": "ok", "llm_configured": true, "search_provider": "tavily", "stt_provider": "openai", "vector_store": "chroma" }
```

## Auth
### `POST /auth/register` → 201
Body `{ "name": "Ravi", "email": "ravi@example.com", "password": "min 8 chars" }`
Response `{ "access_token": "…", "token_type": "bearer", "user": { "id", "name", "email", "created_at" } }` · 409 if the email exists.

### `POST /auth/login` → 200
Body `{ "email", "password" }` → same as register · 401 wrong credentials · 429 after 10 attempts / 5 min.

### `GET /auth/me` → `User`

## Videos
### `POST /videos/url` → 202
Body `{ "url": "https://www.youtube.com/watch?v=…", "title": "optional" }`
Accepts allowlisted platforms (YouTube, Vimeo, Dailymotion, X, TikTok, Facebook, Instagram: configurable) or direct media links (`.mp4 .webm .mov .mkv .m4v .mp3 .m4a .wav .ogg .aac .flac`). Direct links to private/loopback addresses are refused.
Response `Video`:
```json
{ "id": "9f…", "title": "Youtube video", "source_type": "platform", "source_url": "…", "platform": "youtube",
  "embed_url": "https://www.youtube-nocookie.com/embed/…?enablejsapi=1", "duration": null, "playable": false, "created_at": "…" }
```
Analysis starts immediately. Rate limit: 10 submissions per user per hour.

### `POST /videos/upload` → 202
`multipart/form-data`: `file` (video/audio, ≤ `MAX_UPLOAD_MB`), `title` (optional) → `Video` with `playable: true`.

### `GET /videos/{id}/media-token`
`{ "token": "…", "stream_url": "/api/videos/{id}/stream?token=…" }`. Valid 60 min, for that video only.

### `GET /videos/{id}/stream?token=…`
Streams the stored file. Supports HTTP Range (seeking).

## Analyses
### `GET /analyses/{id}/status` (poll this)
```json
{ "video_id": "…", "status": "verifying", "stage_label": "Checking claims against evidence", "progress": 68, "error": null, "updated_at": "…" }
```

### `GET /analyses/{id}`: full result
```json
{
  "video": { …Video },
  "status": { …Status },
  "transcript": { "language": "en", "full_text": "…", "segments": [{ "id": 0, "start": 0.0, "end": 4.2, "text": "…" }] },
  "claims": [{
    "id": "…", "text": "The Great Wall of China is visible from the Moon with the naked eye.",
    "original_quote": "the Great Wall of China is the only man-made structure visible from the Moon",
    "start": 10.8, "end": 17.5, "claim_type": "scientific", "checkworthiness": 0.9,
    "verification": {
      "verdict": "false", "label": "False", "color": "#dc2626", "confidence": 0.81,
      "explanation": "Astronaut accounts say it cannot be seen with the naked eye [E1][E2].",
      "confidence_breakdown": { "support_weight": 0, "refute_weight": 1.42, "mixed_weight": 0, "relevant_sources": 2,
        "distinct_domains": 2, "evidence_strength": 0.69, "agreement": 1.0, "source_diversity": 0.67, "model_suggestion": "false" },
      "adjusted": false
    },
    "evidence": [{ "id": "…", "title": "…", "url": "…", "source_name": "Nasa", "snippet": "…", "stance": "refutes",
      "quote": "…verbatim sentence…", "relevance": 0.71, "credibility": 0.9, "published": null }]
  }],
  "timeline": [{ "claim_id": "…", "start": 10.8, "end": 17.5, "verdict": "false", "color": "#dc2626", "label": "False", "text": "…" }],
  "summary": { "total_claims": 5, "counts": { "verified": 1, "false": 2, "misleading": 1, "unverified": 1 },
    "truth_score": 41.2, "overall_rating": "Mostly Inaccurate", "overall_explanation": "Of 5 claims: …" }
}
```
Claims appear while status is `verifying`. `verification` is null until each one is checked.

### `GET /analyses?page=1&page_size=10&status=completed&q=budget`
`{ "items": [HistoryItem], "total": 12, "page": 1, "page_size": 10 }`

### `GET /analyses/stats`
`{ "total_analyses": 12, "completed": 10, "total_claims": 87, "verdict_counts": { "verified": 40, "false": 18, "misleading": 15, "unverified": 14 } }`

### `POST /analyses/{id}/retry` → 202 `Status`
Clears previous results and re-runs. 409 if the analysis is running. 404 if an uploaded file is gone.

### `POST /analyses/{id}/recheck` → 202 `Status`
Re-verifies the existing claims against **fresh** evidence (search cache bypassed). No re-download, transcription or claim extraction. Adds a Truth Fingerprint version (`trigger: "recheck"`) listing any verdict changes. Previous results stay until the new ones are ready. If it fails, the analysis returns to `completed` with `error: "Re-check failed: …"`. 409 if the analysis isn't completed or is running.

`GET /analyses/{id}` now also returns `metrics` for the latest run:
```json
{ "kind": "analysis", "total_seconds": 94.2,
  "stage_seconds": { "capture": 8.1, "transcribe": 21.4, "extract_claims": 9.7, "verify": 55.0 },
  "claims_verified": 12, "audio_minutes": 6.3, "llm_calls": 15, "llm_input_tokens": 41200, "llm_output_tokens": 6100,
  "embedding_calls": 12, "embedding_tokens": 38000, "search_queries": 24, "search_calls": 18, "search_cache_hits": 6,
  "cache_hit_rate": 0.25, "estimated_cost_usd": null }
```
(Illustrative shape. `estimated_cost_usd` is null unless `PRICE_*` variables are set.)

### `DELETE /analyses/{id}` → 204
Deletes the analysis, all results and the stored file. 409 if the analysis is running.

## Truth Fingerprint & comparison
Full details: [TRUTH_FINGERPRINT.md](TRUTH_FINGERPRINT.md).

### `GET /analyses/{id}/fingerprint`
```json
{ "fingerprint_id": "LTS-7F3A-91C2-04BD", "content_hash": "9f86d081884c7d65",
  "video": { "id": "…", "title": "…", "duration": 52.0 }, "total_claims": 5,
  "counts": { "verified": 1, "false": 2, "misleading": 1, "unverified": 1 },
  "truth_score": 41.2, "overall_rating": "Mostly Inaccurate",
  "evidence_quality": { "score": 58.3, "grade": "C", "label": "Moderate", "coverage": 0.8, "avg_credibility": 0.7,
    "source_diversity": 0.27, "avg_confidence": 0.78, "grounded_sources": 4, "distinct_domains": 1, "fact_checker_sources": 0 },
  "timestamps": [{ "claim_id": "…", "start": 10.8, "end": 17.5, "verdict": "false" }],
  "claims": [{ "claim_id": "…", "text": "…", "start": 10.8, "verdict": "false", "confidence": 0.86,
               "sources": [{ "url": "…", "domain": "en.wikipedia.org", "stance": "refutes", "credibility": 0.7 }] }],
  "versions": [{ "version": 1, "content_hash": "…", "verified_at": "…", "truth_score": 41.2, "evidence_grade": "C", "changes": null }],
  "created_at": "…", "updated_at": "…" }
```
404 until the analysis has completed.

### `GET /fingerprints/{fingerprint_id}`
Same response, looked up by the LTS code (case-insensitive, your own videos only).

### `GET /compare?a={videoId}&b={videoId}`
```json
{ "video_a": { "fingerprint_id": "…", "video": {…}, "counts": {…}, "evidence_quality": {…}, "timestamps": […] },
  "video_b": { … },
  "summary": { "shared_claims": 3, "relation_counts": { "agree": 2, "conflict": 1, "partial": 0, "undetermined": 0 },
    "only_in_a": 2, "only_in_b": 0, "avg_evidence_overlap": 1.0, "shared_domains": ["en.wikipedia.org"],
    "has_conflicts": true, "headline": "3 shared claims, 2 consistent, 1 conflicting. 1 uses different figures." },
  "matches": [{
    "claim_a": { "claim_id": "…", "text": "The Great Wall … is visible from the Moon …", "start": 10.8, "verdict": "false", "confidence": 0.86 },
    "claim_b": { "claim_id": "…", "text": "The Great Wall … cannot be seen from the Moon …", "start": 5.0, "verdict": "verified", "confidence": 0.8 },
    "similarity": 0.89, "match_method": "semantic", "relation": "conflict", "relation_label": "Conflicting",
    "contradictory": true, "different_figures": null,
    "evidence": { "relation": "same_evidence", "label": "Same evidence", "url_overlap": 1.0, "domain_overlap": 1.0,
      "shared_sources": [{ "url": "…", "domain": "en.wikipedia.org", "stance_a": "refutes", "stance_b": "supports" }],
      "only_a": [], "only_b": [], "stance_conflicts": [{ "url": "…", "video_a": "refutes", "video_b": "supports" }] },
    "insight": "The videos conflict: … The same source (en.wikipedia.org) supports one version and refutes the other, so the two videos are stating opposite things." }] }
```
422 `same_video` if a = b · 404 if either has no fingerprint or isn't yours.

### `GET /compare/candidates?video_id={id}&limit=20`
`[{ "video_id", "fingerprint_id", "title", "total_claims", "shared_claims", "updated_at" }]`, sorted by shared claims.

## Advanced features

| Method | Path | Purpose |
|---|---|---|
| PATCH | `/auth/me` | Update `name`, `preferred_language` (`en`/`hi`/`te`) |
| GET | `/analyses/{id}/translation?lang=hi` | Claims, explanations, summary in the chosen language (cached; number-checked) |
| POST | `/deepfake/analyse` `{video_id}` | Start media authenticity analysis (202) |
| GET | `/deepfake/{video_id}` | `{status: not_started/queued/running/completed/failed, result}`; `result.outcome` ∈ possible_manipulation / no_obvious_indicators / inconclusive, with `indicators`, `checks`, `limitations` |
| GET | `/evidence-graph/{video_id}?include_related=true` | `{nodes, edges, stats}` for React Flow |
| POST | `/reports/generate` `{video_id}` | Build the PDF → `{report_id, download_url, fingerprint_id, version}` |
| GET | `/reports?video_id=` | List your reports |
| GET | `/reports/{report_id}` | Download PDF |
| POST | `/verification/check` `{claim}` | Check one typed claim (not stored; 30/hour) |

Claims now include `code` (CLM001…), `text` (original language), `text_en`, `language`, `context_analysis` (`flags`, `risk`, `missing_context`). Evidence includes `trust_score` and `trust` (`level`, `signals[]` with reasons). `GET /analyses/{id}` adds `context_summary` (`contradictions[]`).

### Endpoint paths from the project brief (aliases)
| Brief path | Served by |
|---|---|
| `POST /api/videos/analyse` | same as `POST /api/videos/url` |
| `GET /api/videos/{video_id}` | video details |
| `GET /api/videos/history` | same as `GET /api/analyses` |
| `POST /api/transcription/process` `{video_id}` | re-run the analysis (retry) |
| `GET /api/transcription/{video_id}` | transcript with segments |
| `GET /api/claims/{video_id}` · `GET /api/claims/{claim_id}` | claims of a video, or one claim |
| `POST /api/verification/check` · `GET /api/verification/{video_id}` | ad-hoc check · claims with verdicts |
| `GET /api/timeline/{video_id}` | `{duration, items, summary}` |
| `GET /api/fingerprint/{video_id}` · `POST /api/fingerprint/compare` `{video_a, video_b}` | fingerprint · comparison |
| `POST /api/deepfake/analyse` · `GET /api/evidence-graph/{video_id}` · `POST /api/reports/generate` · `GET /api/reports/{report_id}` | as above |
