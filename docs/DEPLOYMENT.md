# Testing & Deployment

## Testing

### Backend (Pytest)
```bash
cd backend && pip install -r requirements-dev.txt && pytest -q
```
| Suite | Covers |
|---|---|
| `test_media.py` | YouTube id parsing, platform allowlist, look-alike domains, SSRF guard, upload extensions |
| `test_claims.py` | windowing overlap, fuzzy quote matching, hallucinated claim rejection, timestamp mapping, dedupe/ranking |
| `test_verification.py` | fake-quote rejection, insufficient-evidence rules, model-vs-evidence overrides, confidence monotonicity, citation cleaning |
| `test_timeline_search_vectors.py` | timeline colours/order, summary ratings, credibility tiers, result dedupe, chunking, cosine retrieval |
| `test_fingerprint_compare.py` | fingerprint counts/timestamps, unique id, content hash changes, evidence grade, history diff, figure extraction, claim matching (lexical + semantic), conflict / same-evidence / opposite-stance detection |
| `test_metrics_cache.py` | per-run metrics, task isolation, cost estimate from configured prices, cache keys |
| `test_api_and_pipeline.py` | register/login/me, auth required, URL submit + history, cross-user isolation, upload validation, **full pipeline end-to-end with fake Whisper/LLM/search**, fingerprint recording + version history on re-run, run metrics, evidence re-check (no re-transcription, cache bypass, verdict change recorded, failed re-check leaves results intact), scheduler selection, fingerprint/compare endpoints, failure recording |

No API keys or network are needed: integration tests use `mongomock-motor` and deterministic fakes.

### Frontend (Vitest + Testing Library)
```bash
cd frontend && npm install && npm test
```
Covers format utilities, timeline segment rendering and click-to-select, claim card verdict/confidence/seek, citation-to-evidence expansion, form submit and error display.

### API (Postman)
Import `postman/LiveTruthShield.postman_collection.json`. Run **Auth → Login** (or Register): the token is saved automatically. Then run **Videos → Submit URL** and **Analyses → Status** until `completed`. Negative cases (401, 422) have assertions.

### Error scenarios
See `samples/README.md` for a table of failure cases and expected behaviour.

## Speed, cost and re-checks
- **Run metrics:** every analysis stores stage timings, LLM/embedding/search call counts, tokens and cache hits (shown in the *Run stats* panel). Set `PRICE_LLM_INPUT_PER_1M`, `PRICE_LLM_OUTPUT_PER_1M`, `PRICE_EMBEDDING_PER_1M`, `PRICE_STT_PER_MINUTE` and `PRICE_SEARCH_PER_CALL` to your providers' **current** prices to get a cost estimate per run. Prices aren't hard-coded because they change.
- **Evidence cache:** search results are cached in MongoDB (`search_cache`, TTL index) for `SEARCH_CACHE_HOURS` (default 72). Retries and repeated demo runs reuse them, which saves search credits. Re-checks always bypass the cache.
- **Re-check evidence:** the button on the Truth Fingerprint card (or `POST /api/analyses/{id}/recheck`) re-verifies existing claims with fresh evidence in a fraction of the time of a full run.
- **Scheduled re-checks:** set `RECHECK_INTERVAL_HOURS` (e.g. `24`) to re-verify completed analyses automatically, `RECHECK_BATCH` at a time. Each re-check adds a fingerprint version, so verdict changes over time are tracked without anyone pressing a button. Seeded sample analyses are excluded. Run one backend instance while this is on.

## Environment variables
See `backend/.env.example` (all documented). Required in production: `APP_ENV=production`, `JWT_SECRET` (≥32 random chars; startup fails otherwise), `MONGO_URI`, `OPENAI_API_KEY`, plus the search key for your provider and `CORS_ORIGINS` set to your frontend origin.
Frontend: `VITE_API_URL` (empty when served behind the bundled nginx), `VITE_MAX_UPLOAD_MB`.

## Docker
```bash
cp backend/.env.example backend/.env    # fill in secrets
docker compose up --build -d
docker compose logs -f backend
```
- `frontend` (nginx :8080) serves the SPA and proxies `/api` to `backend:8000`, so there are no CORS issues in production.
- Volumes: `mongo_data` (database), `media_data` (uploads + Chroma index).

## Deployment options
| Target | How |
|---|---|
| Single VM (fastest for a hackathon) | Install Docker, clone, `docker compose up -d`, put Caddy/nginx with Let's Encrypt in front of :8080 |
| Render / Railway | Backend as a Docker web service (attach a disk at `/data`), frontend as a static site (`npm run build`, publish `dist`, set `VITE_API_URL`), MongoDB Atlas free tier |
| Vercel + backend host | Frontend on Vercel (`VITE_API_URL=https://api…`, add a rewrite of all routes to `/index.html`), backend on Render/Fly/Railway |

Run **one backend instance** while analyses run in-process. To scale horizontally, move `pipeline.run_analysis` to a worker (Arq/Celery + Redis). Progress already lives in MongoDB, so any API replica can serve status.

## Security
Implemented:
- bcrypt password hashing (cost 12). JWTs with type claims (access vs media) and expiry. Production refuses to start with a weak secret.
- Ownership filter (`user_id`) on every query. Test proves users can't read each other's analyses.
- URL allowlist with exact/sub-domain matching. Direct-link **SSRF protection** (private, loopback, link-local and reserved IPs refused). Redirects not followed on direct downloads.
- Upload extension allowlist, streaming size limit, files stored under generated names (no user-controlled paths).
- yt-dlp runs without cookies or credentials, so only public content is captured. No DRM bypass.
- Rate limits on login and on analysis submission. Generic 500 messages (stack traces only in logs).
- Security headers (`nosniff`, `Referrer-Policy`, `X-Frame-Options` via nginx). CORS restricted to configured origins.
- Temporary audio deleted after each run. Per-analysis vector collections dropped after each run.

Recommended before real users:
- Serve only over HTTPS. Consider httpOnly secure cookies plus CSRF protection instead of `localStorage` tokens.
- Add refresh tokens / revocation, email verification and password reset.
- Move rate limiting to Redis. Put a WAF or CDN in front.
- Scan uploads (e.g. ClamAV) and run FFmpeg in a sandboxed worker with CPU/memory limits.
- Set per-user monthly quotas on LLM/search spend. Alert on cost anomalies.
- MongoDB auth + TLS, least-privilege DB user, encrypted backups.
- Add a privacy policy and a retention job that deletes old uploads.
- Log prompts and outputs for audit, with PII redaction.

## Step-by-step setup

### 1. Python 3.12 environment
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```
### 2. Node.js 20+
Install from nodejs.org (or `nvm install 20`), then `cd frontend && npm install`.
### 3. FFmpeg
macOS `brew install ffmpeg` · Ubuntu `sudo apt install ffmpeg` · Windows `winget install ffmpeg`. Check: `ffmpeg -version`.
### 4. MongoDB Atlas (free tier)
1. Create an account at mongodb.com/atlas → **Build a database** → free shared cluster.
2. **Database Access** → add a user with a strong password (readWrite on your database).
3. **Network Access** → add your IP (and your backend host's outbound IP in production).
4. **Connect → Drivers** → copy the `mongodb+srv://…` string into `MONGO_URI` (put the password in; URL-encode special characters).
Indexes, including the cache TTL, are created automatically on first start.
### 5. API keys
`OPENAI_API_KEY` (or any OpenAI-compatible provider via `OPENAI_BASE_URL`), `TAVILY_API_KEY` (or `SEARCH_PROVIDER=wikipedia`), and a random `JWT_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(64))"`). Keys stay in `backend/.env`, never in frontend code.
### 6. Run
```bash
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev                 # http://localhost:5173
python -m scripts.seed_demo                # optional demo data
```

## Production deployment
- **Backend on Render:** New → Web Service → connect the repo, root `backend`, runtime Docker (uses `backend/Dockerfile`). Add a persistent disk mounted at `/data`, set env vars from `.env.example` (`APP_ENV=production`, `MONGO_URI` from Atlas, keys, `CORS_ORIGINS=https://<your-vercel-app>`). One instance.
- **Frontend on Vercel:** import the repo, root `frontend`, framework Vite, env `VITE_API_URL=https://<your-render-service>`. Add `vercel.json` with a rewrite of `/(.*)` to `/index.html` (included).
- **Single VM alternative:** `docker compose up -d --build` behind Caddy/nginx with HTTPS.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `service_not_configured` / analysis fails at once | `OPENAI_API_KEY` or search key missing; check `GET /api/health` |
| "ffmpeg is not installed on the server" | install FFmpeg and restart; in Docker it's preinstalled |
| YouTube link fails "requires signing in" | the video is age-restricted, private or members-only (by design); upload the file instead |
| Everything comes back "Insufficient Evidence" | search provider returns little content: use Tavily; check `MIN_EVIDENCE_SCORE` (0.35); claims may be too local or recent |
| CORS error in browser | add the frontend origin to `CORS_ORIGINS` (dev uses the Vite proxy, so no CORS) |
| Atlas `ServerSelectionTimeoutError` | IP not in Network Access, or a wrong password/encoding in `MONGO_URI` |
| Face / lip-sync "not assessed (OpenCV face model not found)" | `pip install opencv-python-headless==4.10.0.84` (some builds omit the Haar cascades) |
| Hindi/Telugu text shows boxes in PDF | expected: PDFs use English translations; the app shows the original script |
| Re-check says "already running" | wait for the current job; restart clears stale state (interrupted re-checks return to completed) |
| Slow analyses | lower `MAX_CLAIMS_PER_VIDEO`, set `CONTEXT_ANALYSIS=false`, keep `SEARCH_CACHE_HOURS` on, use `STT_PROVIDER=openai` |
