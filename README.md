# LiveTruth Shield
*Verify Before You Believe. Think Before You Share.*

**AI-powered video fact verification.** Paste a video link or upload a file. LiveTruth Shield transcribes the speech, extracts the factual claims with timestamps, checks each one against retrieved evidence, and shows verdicts, sources and a colour-coded truth timeline.

> Help people question information before believing or sharing it.

| Step | What happens | Where in the code |
|---|---|---|
| 1. Capture | Validate URL / accept upload → download (yt-dlp) → extract 16 kHz mono audio (FFmpeg) | `backend/app/services/media.py` |
| 2. Understand | Whisper transcription with timestamps → LLM claim extraction, grounded to transcript segments | `transcription.py`, `claims.py` |
| 3. Verify | Web search → chunk + embed passages (RAG) → LLM stance judgement with verbatim quotes → evidence-based verdict and confidence | `search.py`, `vectorstore.py`, `verification.py` |
| 4. Show | Timeline, summary, claim cards, evidence panel, click-to-seek | `timeline.py`, `frontend/src/components/analysis/*` |

**Advanced features** (details in [docs/ADVANCED_FEATURES.md](docs/ADVANCED_FEATURES.md); status in [docs/FEATURE_CHECKLIST.md](docs/FEATURE_CHECKLIST.md)):
- **Multilingual:** Telugu, Hindi and English. Claims kept in the original language with an English translation, multilingual search, results in your language.
- **Source Trust Analyser:** publisher, primary source, author, date, references, corroboration, with reasons, never reputation alone.
- **Context Manipulation Detector:** out-of-context statements, selective quotes, misleading statistics, missing information, self-contradictions.
- **Media authenticity:** signal checks for splices, timing gaps, lip-sync and face consistency, reported as possible manipulation, no obvious indicators, or inconclusive.
- **Evidence graph** (React Flow), **PDF fact-check reports**, and a **quick single-claim check**.

**Truth Fingerprint:** every analysed video gets a unique `LTS-XXXX-XXXX-XXXX` fingerprint with claim counts, verdicts, an evidence-quality grade, original timestamps and a verification history. Compare two videos to see which claims they share, whether they rely on the same evidence, and where they conflict. See [docs/TRUTH_FINGERPRINT.md](docs/TRUTH_FINGERPRINT.md).

**Tracking over time:** *Re-check evidence* re-verifies a video's claims against fresh sources, and optional scheduled re-checks do it automatically. Each run records timings, API usage and an optional cost estimate, and search results are cached to save credits.

Verdicts: 🟢 **Verified** · 🔴 **False** · 🟡 **Misleading** · ⚪ **Insufficient Evidence** (returned whenever the evidence can't support a decision; the system never guesses).

---

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/allacheruvuvenkatarakesh-cpu/frontend)

**Going live:** follow [docs/GO_LIVE.md](docs/GO_LIVE.md): GitHub → MongoDB Atlas → Render Blueprint (`render.yaml`) in about an hour.

## Quick start (local)

### Prerequisites
- Python 3.11+ · Node.js 20+ · FFmpeg (`ffmpeg -version`) · MongoDB 6+ (local or Atlas)
- An OpenAI API key (or any OpenAI-compatible endpoint) and a Tavily API key (free tier works). For a no-key search fallback, set `SEARCH_PROVIDER=wikipedia`.

```bash
# Install FFmpeg + MongoDB if needed
# macOS:   brew install ffmpeg mongodb-community && brew services start mongodb-community
# Ubuntu:  sudo apt install ffmpeg   (MongoDB: https://www.mongodb.com/docs/manual/installation/)
# Windows: winget install ffmpeg    (MongoDB Community Server installer)
# Or just: docker run -d -p 27017:27017 --name mongo mongo:7
```

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                     # then fill in OPENAI_API_KEY, TAVILY_API_KEY, JWT_SECRET
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

Optional demo data (works without API keys):
```bash
python -m scripts.seed_demo        # login: demo@livetruth.app / DemoPass123!  (2 videos that share claims → try Compare)
                                   # fixed demo fingerprints: LTS-FC2D-EF48-490D and LTS-782E-9337-82D3 (match the pitch deck)
```

### Frontend
```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173 (proxies /api to :8000)
```

### Docker (everything)
```bash
cp backend/.env.example backend/.env   # fill in keys
docker compose up --build              # app: http://localhost:8080  API: http://localhost:8000/docs
docker compose exec backend python -m scripts.seed_demo   # optional demo data
```

### Tests
```bash
cd backend && pytest -q          # unit + API + full pipeline with fakes (no keys/network needed)
cd frontend && npm test          # Vitest + Testing Library
```
Postman: import `postman/LiveTruthShield.postman_collection.json`.

---

## Project structure (where every file goes)
```
livetruth-shield/
├── docker-compose.yml               Mongo + backend + frontend
├── backend/
│   ├── Dockerfile                   python:3.12-slim + ffmpeg
│   ├── requirements.txt / -dev.txt
│   ├── .env.example                 all configuration, documented
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py                  FastAPI app, middleware, error handlers, router mount
│   │   ├── core/
│   │   │   ├── config.py            pydantic-settings, env parsing
│   │   │   ├── security.py          bcrypt hashing, JWT access + media tokens
│   │   │   ├── exceptions.py        domain errors → HTTP codes
│   │   │   └── logging.py           text / JSON logging
│   │   ├── db/mongo.py              Motor client, collection names, indexes
│   │   ├── models/schemas.py        Pydantic models + enums (Verdict, Stance, Status…)
│   │   ├── api/
│   │   │   ├── deps.py              current-user dependency, rate limiters
│   │   │   ├── serializers.py       Mongo docs → API models
│   │   │   └── routes/
│   │   │       ├── auth.py          /api/auth/*
│   │   │       ├── videos.py        /api/videos/* (URL, upload, media token, stream)
│   │   │       ├── analyses.py      /api/analyses/* (detail, status, history, stats, retry, delete)
│   │       ├── fingerprints.py  /api/analyses/{id}/fingerprint, /api/fingerprints/{code}, /api/compare*
│   │       └── features.py      /api/deepfake, /api/evidence-graph, /api/reports, /api/verification/check, brief-style aliases
│   │   └── services/
│   │       ├── media.py             Step 1: URL rules, SSRF guard, yt-dlp, FFmpeg
│   │       ├── transcription.py     Step 2a: Whisper API / faster-whisper
│   │       ├── claims.py            Step 2b: claim extraction, grounding, dedupe, ranking
│   │       ├── llm.py               OpenAI-compatible chat (JSON) + embeddings, retries
│   │       ├── search.py            Step 3a: Tavily / Serper / Wikipedia + credibility tiers
│   │       ├── vectorstore.py       Step 3b: chunking + Chroma / in-memory vector index
│   │       ├── verification.py      Step 3c: stance grounding, verdict rules, confidence
│   │       ├── timeline.py          Step 4: timeline + overall summary
│       ├── fingerprint.py       Truth Fingerprint: evidence quality, content hash, version history
│       ├── compare.py           two-video comparison: claim matching, conflicts, evidence overlap
│       ├── metrics.py           per-run timings, API call/token counts, optional cost estimate
│       ├── trust.py             Source Trust Analyser (multi-signal, with reasons)
│       ├── textnorm.py          Unicode-aware normalisation (Telugu/Hindi safe), language codes
│       ├── translate.py         result translation (cached, number-preservation guard)
│       ├── context.py           Context Manipulation Detector + in-video contradictions
│       ├── authenticity.py      media authenticity signal checks (FFmpeg + OpenCV)
│       ├── graph.py             evidence relationship graph
│       ├── report.py            PDF fact-check report (ReportLab)
│   │       └── pipeline.py          orchestration, progress, recovery
│   ├── scripts/seed_demo.py         demo user + labelled sample analysis
│   └── tests/                       pytest suites + fixtures/sample_transcript.json
├── frontend/
│   ├── Dockerfile, nginx.conf       production build served by nginx, /api proxied
│   ├── package.json, vite.config.js, tailwind.config.js, postcss.config.js, index.html
│   └── src/
│       ├── main.jsx, App.jsx, index.css
│       ├── api/client.js, endpoints.js      fetch wrapper, upload progress, endpoints
│       ├── context/AuthContext.jsx          session state
│       ├── hooks/useAnalysis.js             load + poll analysis
│       ├── utils/format.js                  verdict colours, time formatting, citations
│       ├── components/
│       │   ├── ui/index.jsx                 Button, Logo, VerdictBadge, ConfidenceMeter…
│       │   ├── layout/AppLayout.jsx, ProtectedRoute.jsx
│       │   ├── dashboard/SubmitVideoForm.jsx, StatsPanel.jsx, AnalysisList.jsx
│       │   ├── fingerprint/FingerprintGlyph.jsx, TruthFingerprintCard.jsx
│       │   └── analysis/VideoPlayer.jsx, ProgressTracker.jsx, TruthTimeline.jsx,
│       │                ClaimCard.jsx, EvidencePanel.jsx, TranscriptViewer.jsx, SummaryPanel.jsx
│       ├── pages/LandingPage, AuthPages, DashboardPage, AnalysisPage, HistoryPage, ComparePage,
│       │        FingerprintPage, AuthenticityPage, GraphPage, ProfilePage, NotFoundPage
│       └── test/                            Vitest specs
├── docs/
│   ├── ARCHITECTURE.md   system + data-flow diagrams, frontend/backend/auth architecture
│   ├── DATABASE.md       collections, schemas, relationships, indexes
│   ├── API.md            endpoint reference
│   ├── AI_PIPELINE.md    the 8 AI stages explained
│   ├── TRUTH_FINGERPRINT.md  fingerprint contents, evidence grade, history, comparison logic
│   ├── ADVANCED_FEATURES.md  trust, multilingual, context, authenticity, graph, report
│   ├── FEATURE_CHECKLIST.md  completed / pending features and how each was verified
│   ├── DEPLOYMENT.md     testing, Docker, env vars, production security
│   └── PITCH.md          problem → solution, 10 slides, judge Q&A, 2-minute demo script
├── postman/              Postman collection
└── samples/              sample script, demo-video guidance, error scenarios
```

## Configuration
All settings live in `backend/.env` (see `.env.example`). Main switches:

| Variable | Options | Notes |
|---|---|---|
| `LLM_MODEL` | `gpt-4o-mini` (default), any chat model | `OPENAI_BASE_URL` lets you point at Groq, Together, vLLM, Ollama… |
| `STT_PROVIDER` | `openai` / `local` | `local` runs faster-whisper on your machine (no audio leaves it) |
| `SEARCH_PROVIDER` | `tavily` / `serper` / `wikipedia` | Tavily gives the best evidence quality |
| `VECTOR_STORE` | `chroma` / `memory` | `memory` needs no extra service |
| `SEARCH_CACHE_HOURS` | int (72) | reuse search results; 0 disables |
| `TRUST_FETCH_METADATA` | bool (true) | fetch cited pages for author/date/reference signals |
| `CONTEXT_ANALYSIS` | bool (true) | context manipulation + contradiction checks |
| `EMBEDDING_PROVIDER` | `openai` / `local` | `local` = multilingual Sentence Transformers |
| `RETENTION_DAYS` | int (0) | delete stored videos/reports after N days |
| `RECHECK_INTERVAL_HOURS` | int (0) | automatic evidence re-checks; 0 disables |
| `PRICE_*` | floats (0) | your providers' current prices → cost estimate per run |
| `MAX_VIDEO_MINUTES`, `MAX_CLAIMS_PER_VIDEO` | ints | cost and latency controls |

## Responsible use
- Only public content is captured: no cookies, logins, DRM circumvention or private videos. Users are responsible for having the right to analyse what they submit. Respect each platform's terms.
- Verdicts are decision support, not final rulings. Every verdict links to the passages it rests on, and the UI says so.
- Audio is deleted after transcription. Uploaded files are kept for playback until the user deletes the analysis.
