# System Architecture

## 1. System architecture

```mermaid
flowchart LR
  subgraph Client["Browser — React SPA"]
    UI[Pages & components]
    AC[AuthContext]
    API[api/client.js]
  end

  subgraph Edge["nginx (prod) / Vite proxy (dev)"]
    NG[/static files + /api proxy/]
  end

  subgraph Backend["FastAPI (uvicorn)"]
    R[Routes: auth · videos · analyses]
    D[Deps: JWT auth, rate limit]
    P[Pipeline orchestrator<br/>asyncio background task]
    subgraph S[Services]
      M[media.py<br/>yt-dlp · FFmpeg]
      T[transcription.py<br/>Whisper]
      C[claims.py]
      SR[search.py]
      V[vectorstore.py]
      VF[verification.py]
      TL[timeline.py]
      FP[fingerprint.py · compare.py]
    end
  end

  DB[(MongoDB)]
  FS[(File storage<br/>videos/ audio/ chroma/)]
  OAI[[LLM + Embeddings + Whisper API]]
  WEB[[Search API<br/>Tavily / Serper / Wikipedia]]
  PLAT[[Video platforms]]

  UI --> AC --> API --> NG --> R
  R --> D
  R --> DB
  R -- schedule --> P
  P --> M --> PLAT
  M --> FS
  P --> T --> OAI
  P --> C --> OAI
  P --> SR --> WEB
  P --> V --> FS
  V --> OAI
  P --> VF --> OAI
  P --> TL
  P --> FP
  R --> FP
  P --> DB
```

## 2. Data flow (one analysis)

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant FE as React
  participant API as FastAPI
  participant DB as MongoDB
  participant PL as Pipeline
  participant EXT as Whisper / LLM / Search

  U->>FE: paste URL or choose file
  FE->>API: POST /api/videos/url | /upload (Bearer JWT)
  API->>API: validate URL (allowlist, SSRF guard) or file type/size
  API->>DB: insert videos + analysis_history(status=queued)
  API-->>FE: 202 {video id}
  API->>PL: schedule_analysis(video_id)
  FE->>API: poll GET /analyses/{id}/status every 2.5 s

  PL->>DB: status=capturing (5%)
  PL->>PL: yt-dlp / download / upload → FFmpeg → 16 kHz mono MP3
  PL->>DB: status=transcribing (20%)
  PL->>EXT: Whisper (chunks ≤10 min)
  PL->>DB: transcripts {segments[start,end,text]}
  PL->>DB: status=extracting_claims (40%)
  PL->>EXT: LLM per transcript window → claims with segment ids
  PL->>PL: ground quotes, map timestamps, dedupe, rank
  PL->>DB: claims[]
  loop each claim (3 in parallel) — 50%→95%
    PL->>EXT: search (plain + "fact check" query)
    PL->>EXT: embed claim + passages
    PL->>PL: vector index add + top-k retrieval
    PL->>EXT: LLM stance per passage with verbatim quotes
    PL->>PL: discard ungrounded quotes → weighted verdict + confidence
    PL->>DB: verification_results + evidence_sources
  end
  PL->>DB: timeline + summary, status=completed (100%)
  PL->>DB: truth_fingerprints (new version + changes)
  FE->>API: GET /analyses/{id}
  API-->>FE: video, transcript, claims+verdicts+evidence, timeline, summary
  U->>FE: click timeline segment → player seeks to timestamp
```

## 3. Frontend architecture
- **Routing** (`App.jsx`): public `/`, `/login`, `/register`; protected `/dashboard`, `/analysis/:videoId`, `/history` wrapped in `ProtectedRoute` + `AppLayout` (sidebar on desktop, drawer on mobile).
- **State**: `AuthContext` holds the user and token (stored in `localStorage`, read via `tokenStore`). Page-level state otherwise; no global store needed.
- **Data access**: `api/client.js` adds the bearer token, normalises errors into `ApiError(message, status, code)`, signs out on 401. `uploadWithProgress` uses XHR for upload progress.
- **Live progress**: `useAnalysis` polls `/status` (cheap) and only refetches the full result when progress changes, so claims appear as they're verified. Stops when completed or failed. A retry restarts it.
- **Analysis view**: `VideoPlayer` exposes `seekTo()` through a ref and works for streamed files (`<video>` + media token), YouTube/Vimeo embeds (postMessage), or a link-out fallback. `TruthTimeline`, `TranscriptViewer` and `ClaimCard` all call the same `seek` + `selectClaim` callbacks, so the views stay in sync.
- **Design system**: Tailwind theme with `navy` scale, off-white `paper` background, `card` component class, verdict colours shared through `utils/format.js`. Framer Motion for tab, list and timeline transitions (respects `prefers-reduced-motion`). Recharts for the dashboard donut and summary bars.

## 4. Backend architecture
Layered so each part is testable on its own:

| Layer | Responsibility |
|---|---|
| `api/routes` | HTTP only: parse input, check ownership, call services, serialise |
| `api/deps` | authentication, rate limiting |
| `services` | all domain logic; raise `AppError` subclasses, never `HTTPException` |
| `db/mongo` | connection, collection names, indexes |
| `core` | config, security, errors, logging |

- **Error handling**: every `AppError` becomes `{"error": {"code", "message", "details"}}` with the right status; validation errors use the same shape; unexpected errors are logged with a stack trace and return a generic 500.
- **Background work**: `pipeline.schedule_analysis` starts an asyncio task; blocking work (FFmpeg, yt-dlp, local Whisper) runs in `asyncio.to_thread`. Progress is written to `analysis_history`, so any API instance can serve status. Analyses interrupted by a restart are marked failed on startup and can be retried. For scale, move `run_analysis(video_id)` into a queue worker (Arq/Celery). Its interface already takes only an id.
- **Logging**: request id, method, path, status and latency per request. JSON logs in production.

## 5. AI processing pipeline
See [AI_PIPELINE.md](AI_PIPELINE.md) for each stage in detail.

```mermaid
flowchart TB
  A[Audio] --> B[Whisper STT<br/>segments + timestamps]
  B --> C[Windowing<br/>3.5k chars, 2-segment overlap]
  C --> D[LLM claim extraction<br/>segment-id references]
  D --> E{Quote found in<br/>cited segments?}
  E -- no --> X1[drop]
  E -- yes --> F[Dedupe + rank by check-worthiness]
  F --> G[Search: claim + 'fact check' query]
  G --> H[Credibility scoring + blocklist]
  H --> I[Chunk → embed → vector index]
  I --> J[Top-k semantic retrieval<br/>sim ≥ threshold, ≤2 per URL]
  J --> K[LLM stance per passage<br/>+ verbatim quote]
  K --> L{Quote in passage?}
  L -- no --> X2[treat as irrelevant]
  L -- yes --> M[Weighted support / refute / mixed]
  M --> N{Enough evidence?<br/>Model verdict consistent?}
  N -- no --> O[Insufficient Evidence<br/>or downgrade]
  N -- yes --> P[Verdict + computed confidence]
  O --> Q[Timeline + summary]
  P --> Q
```

## 6. Authentication architecture

```mermaid
sequenceDiagram
  participant FE as React
  participant API as FastAPI
  participant DB as MongoDB
  FE->>API: POST /auth/register {name,email,password}
  API->>API: bcrypt(cost 12)
  API->>DB: users.insert (unique email index)
  API-->>FE: {access_token (JWT HS256, 2h), user}
  FE->>FE: store token, set user
  FE->>API: any request · Authorization: Bearer <jwt>
  API->>API: decode, check exp + typ=access
  API->>DB: load user by sub
  Note over FE,API: Media playback
  FE->>API: GET /videos/{id}/media-token
  API-->>FE: JWT typ=media, vid=id, 60 min
  FE->>API: <video src="/videos/{id}/stream?token=…"> (Range requests)
  API->>API: token typ=media and vid matches, ownership check
```
- Passwords: bcrypt, never returned. Login is rate-limited per IP+email.
- Access tokens are stateless JWTs with a `typ` claim, so a media token can't be used as an access token or the other way round.
- Every query filters by `user_id`, so users can only see their own analyses (covered by a test).
- Production hardening options are in [DEPLOYMENT.md](DEPLOYMENT.md#security).

## 7. How components communicate
| From → To | Channel | Format |
|---|---|---|
| Browser → API | HTTPS REST via nginx `/api` | JSON; multipart for uploads; Range for media |
| API → Pipeline | in-process asyncio task | `video_id` |
| Pipeline → MongoDB | Motor (async) | documents per collection |
| Pipeline → OpenAI-compatible API | HTTPS (official SDK) | chat JSON mode, embeddings, audio transcription |
| Pipeline → Search API | HTTPS (httpx) | JSON results |
| Pipeline → platforms | yt-dlp | audio-only stream |
| Pipeline → FFmpeg | subprocess | files on disk |
| Frontend ↔ progress | polling `/status` | small JSON |
