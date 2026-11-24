# Go Live: step by step

About 45–60 minutes the first time. You need: a GitHub account, a MongoDB Atlas account, a Render account (or Vercel + Render), an OpenAI API key and a Tavily API key. Optional: a Google Fact Check Tools API key.

## 0. Run it locally once (catches problems before deploying)
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env     # fill in keys + MONGO_URI
pytest -q                                                       # all tests should pass
uvicorn app.main:app --port 8000
# new terminal
cd frontend && npm install && npm test && npm run dev           # open http://localhost:5173
```
Register, analyse one short public video, open the results. Fix anything that breaks now, not on stage.

## 1. Put the code on GitHub
Already done: the code is in **github.com/allacheruvuvenkatarakesh-cpu/frontend** (the repo holds the whole project: `backend/`, `frontend/`, `docs/`). Merge the `livetruth-shield` pull request into `main`, then skip to step 2. For a fresh copy elsewhere:
```bash
cd livetruth-shield
git init && git add . && git commit -m "LiveTruth Shield"
git branch -M main
git remote add origin https://github.com/<you>/livetruth-shield.git
git push -u origin main
```
The included GitHub Actions workflow runs the backend and frontend tests on every push (the **Actions** tab). Never commit `backend/.env`: `.gitignore` already excludes it.

## 2. Database: MongoDB Atlas (free tier)
1. mongodb.com/atlas → create a free cluster (choose a region near your Render region, e.g. Singapore / Mumbai).
2. Database Access → add user + strong password.
3. Network Access → `0.0.0.0/0` for the hackathon (Render's outbound IPs vary on lower plans); restrict it later.
4. Connect → Drivers → copy `mongodb+srv://…` → this is `MONGO_URI` (URL-encode special characters in the password).

## 3. API keys
| Key | Where | Notes |
|---|---|---|
| `OPENAI_API_KEY` | platform.openai.com → API keys | add billing credit; set a monthly limit |
| `TAVILY_API_KEY` | tavily.com → dashboard | free tier covers a hackathon; search results are cached for 72h |
| `FACTCHECK_API_KEY` (optional) | Google Cloud console → enable **Fact Check Tools API** → Credentials → API key | restrict the key to that API |

## 4. Deploy on Render (backend + frontend in one go)
1. render.com → **New → Blueprint** → connect GitHub → choose the repo. Render reads `render.yaml`.
2. It asks for the `sync: false` values:
   - `livetruth-api`: `MONGO_URI`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `FACTCHECK_API_KEY` (or blank), and `CORS_ORIGINS` (put `https://livetruth-web.onrender.com` for now; correct it after step 3 if Render gives a different name).
   - `livetruth-web`: `VITE_API_URL` = `https://livetruth-api.onrender.com` (same caveat).
3. **Apply.** First build takes ~5–10 minutes.
4. Check the URLs Render assigned. If they differ from the guesses above, update `CORS_ORIGINS` (API) and `VITE_API_URL` (web), then **Manual Deploy** the web service (Vite bakes the URL in at build time).
5. Open `https://<api>/api/health`. You should see `"status":"ok","llm_configured":true`.

**Plans:** `render.yaml` uses the *starter* plan for the API because a persistent disk (uploads, reports) needs a paid instance. For a free demo, delete the `disk:` block and change `plan: starter` to `plan: free`. Uploads and PDF reports then disappear on restart, the free instance sleeps after inactivity (the first request takes ~1 minute to wake), and link-based analyses still work.

**Alternative frontend on Vercel:** import the repo, root directory `frontend`, framework Vite, env `VITE_API_URL=https://<api>`. `vercel.json` already rewrites routes to `index.html`. Put the Vercel URL in the API's `CORS_ORIGINS`.

## 5. Demo data
Render dashboard → `livetruth-api` → **Shell**:
```bash
python -m scripts.seed_demo
```
Login `demo@livetruth.app` / `DemoPass123!`. Two sample videos with fixed fingerprints (`LTS-FC2D-EF48-490D`, `LTS-782E-9337-82D3`) that match the pitch deck. Change that password, or delete the demo user, after the event.

## 6. Pre-demo checklist
- [ ] `/api/health` OK; register + login work on the live URL
- [ ] One real public video analysed end to end; timeline click jumps the video
- [ ] Language switch shows Hindi/Telugu; PDF report downloads
- [ ] Media authenticity runs on an uploaded file
- [ ] Compare shows the two demo videos; evidence graph renders
- [ ] Run stats show plausible timing; set `PRICE_*` to show cost
- [ ] Wake the free instance 5 minutes before presenting (open the site)
- [ ] Backup: the browser prototype (no backend) + a screen recording

## 7. After the event
Rotate `JWT_SECRET` and API keys, restrict Atlas network access, lower OpenAI limits, set `RETENTION_DAYS`.

## Troubleshooting live
| Symptom | Fix |
|---|---|
| Web app shows "Cannot reach the server" | `VITE_API_URL` wrong or set after the build: fix it and redeploy the web service |
| Browser console CORS error | add the exact web URL (https, no trailing slash) to `CORS_ORIGINS`; redeploy the API |
| API crashes at start "JWT_SECRET must be set" | the blueprint generates one; if you created the service by hand, add a 64-character random value |
| Analyses fail "service not configured" | `OPENAI_API_KEY` / `TAVILY_API_KEY` missing on the API service |
| YouTube download errors on the server | some platforms block data-centre IPs; use uploads, or another platform's public link, for the demo |
| Want local Whisper on the server | uncomment `faster-whisper` in `requirements.txt` and set `STT_PROVIDER=local` (needs a larger instance) |
