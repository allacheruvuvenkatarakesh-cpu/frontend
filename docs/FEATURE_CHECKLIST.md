# Feature Checklist

Status against the LiveTruth Shield master brief. Read the **Verified** column honestly:

- **Unit-tested**: logic covered by Pytest/Vitest suites.
- **E2E (fakes)**: the full pipeline ran end to end with fake AI/search providers and an in-memory database.
- **Synthetic media**: tested on videos generated with FFmpeg.
- **Not yet run**: written and syntax-checked, but needs your environment (API keys, `pip/npm install`, MongoDB) for a first real run.

The FastAPI HTTP tests and the React test suite are written but were **not run** in the build environment (packages couldn't be installed). Run `pytest` and `npm test` first.

## Core workflow
| Feature | Status | Verified |
|---|---|---|
| URL submit (allowlist, look-alike rejection, SSRF guard) | ✅ | Unit-tested |
| Upload MP4/MOV/MKV/WebM/audio with size + type checks | ✅ | Unit-tested (validation) · upload route not yet run |
| Metadata, FFmpeg audio extraction, preview player | ✅ | Not yet run (ffmpeg calls unit-tested indirectly) |
| Public-only capture: no cookies, logins or DRM bypass | ✅ | By design (yt-dlp options) |
| Whisper STT (API or local), language detection, timestamps | ✅ | E2E (fakes) |
| Claim extraction, one fact per claim, opinions dropped | ✅ | Unit-tested + E2E (fakes) |
| Claim IDs `CLM001…`, start/end timestamps, language, type, pending state | ✅ | E2E (fakes) |
| Hallucinated-claim and fake-quote rejection | ✅ | Unit-tested |
| Two-query evidence search, cache, credibility + trust | ✅ | Unit-tested |
| RAG: chunk → embed → semantic retrieval (Chroma / in-memory) | ✅ | Unit-tested |
| Stance per source with verified verbatim quotes | ✅ | Unit-tested |
| Verdicts gated by weighted evidence; disagreement → Misleading | ✅ | Unit-tested |
| Insufficient Evidence instead of guessing | ✅ | Unit-tested + E2E (fakes) |
| Computed confidence (never the LLM's) | ✅ | Unit-tested |
| Colour-coded clickable truth timeline, filters, statistics | ✅ | Component test written (not yet run) |

## Innovation features
| Feature | Status | Verified |
|---|---|---|
| **Truth Fingerprint**: unique ID, SHA-256 content hash of canonical record, versions, history of changes | ✅ | Unit-tested + E2E (fakes) |
| Fingerprint comparison: shared claims, conflicts, same/independent evidence, different figures | ✅ | Unit-tested |
| Evidence re-check + scheduled re-checks (new version on change) | ✅ | E2E (fakes) |
| **Multilingual** (Telugu/Hindi/English): original + English claim, multilingual search, translated results, number-preservation guard | ✅ | Unit-tested with real Telugu/Hindi text · translation calls not yet run |
| Local multilingual embeddings (Sentence Transformers) | ✅ optional | Not yet run |
| **Media authenticity**: frame timing, scene cuts, audio splices, digital silence, lip-sync, face consistency; 3 honest outcomes + limitations | ✅ signal checks | Unit-tested + synthetic media (clean → no indicators, spliced → possible manipulation). Face/lip-sync needs `opencv-python-headless` 4.x |
| Trained deepfake classifier / external API | ⏳ extension point (`detector_hook`) | No model or service included |
| **Context manipulation detector**: out-of-context, selective quote, misleading statistic, missing info, incomplete claim, self-contradiction; grounded transcript quotes | ✅ | Unit-tested · LLM calls not yet run |
| **Source trust analyser**: publisher, primary source, author, date, references, transparency, corroboration, with reasons | ✅ | Unit-tested (incl. real HTML parsing) |
| **Evidence relationship graph** (React Flow): video, claims, sources, related claims, contradictions | ✅ | Unit-tested (builder + layout) |
| **PDF report**: video, summary, claims, timestamps, verdicts, evidence + links, fingerprint, contradictions, authenticity, transcript, limitations | ✅ | Unit-tested (PDF generated and text-verified) |
| Ad-hoc single-claim check (`POST /api/verification/check`) | ✅ | Not yet run |

## Platform
| Feature | Status | Verified |
|---|---|---|
| Register / login / logout / protected routes / profile + language | ✅ | Tests written (not yet run) |
| bcrypt, JWT, per-user data isolation | ✅ | Isolation test written (not yet run) |
| Rate limiting (login, analyses, claim checks) | ✅ in-memory | Not yet run (use Redis for multi-instance) |
| Background jobs + polling progress | ✅ | E2E (fakes) |
| Brief's API paths as aliases (`/api/claims`, `/api/timeline`, `/api/fingerprint/compare`, …) | ✅ | Not yet run |
| Run metrics (timings, calls, tokens, cache hits, optional cost) | ✅ | Unit-tested + E2E (fakes) |
| Retention clean-up (`RETENTION_DAYS`) | ✅ | Not yet run |
| Docker Compose, nginx, env templates | ✅ | Not yet run |
| Render Blueprint (`render.yaml`), Vercel config, GitHub Actions CI | ✅ | YAML validated; not yet deployed |
| Role-based access (admin) | ⏳ pending | Single role today |
| WebSockets progress | ⏳ pending | Polling used (simpler, works behind any proxy) |
| Malware scanning of uploads (ClamAV) | ⏳ pending | Type/size checks, safe file names, no execution |
| Axios | ↔ substituted | `fetch` wrapper with the same behaviour (no extra dependency) |
| OpenCV ✅ · MoviePy ↔ not needed | | FFmpeg covers the editing needs |
| YouTube Data API | ⏳ not integrated | yt-dlp reads public metadata. The official API needs a key and quota; add if your judges require it |
| Fact-check databases (Google Fact Check Tools API, ClaimReview) | ✅ optional (`FACTCHECK_API_KEY`) | Response parser unit-tested; live API not yet called |

## Known limitations (say these to judges)
- Signal-based authenticity checks can't catch high-quality deepfakes, and ordinary editing triggers indicators.
- Translations are machine-generated (verdicts never depend on them). Have a native speaker review the Hindi/Telugu UI labels.
- PDF reports show non-English claims in English, because ReportLab can't shape Indic scripts.
- Comparison and the graph's "related claims" only cover the user's own videos.
- One backend instance while scheduled re-checks or in-process jobs are on.
