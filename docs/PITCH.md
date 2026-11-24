# Hackathon Presentation Kit

**Tagline:** *Verify Before You Believe. Think Before You Share.*

## Positioning
> **LiveTruth Shield is not just a fact-checking tool. It's a video credibility and evidence-tracking platform.**

A fact-checker answers *"Is this claim true?"* once, and forgets. LiveTruth Shield answers three bigger questions, and remembers:
1. **How credible is this video**, claim by claim and second by second?
2. **What evidence is it built on**, and how strong is that evidence?
3. **How does it relate to other videos** making the same claims, and how do verdicts change over time?

| A fact-checking tool… | A credibility and evidence-tracking platform… | LiveTruth Shield |
|---|---|---|
| checks a claim once | **records** every check | Verification history: every run is a version with a content hash |
| gives a verdict | measures **how strong the evidence is** | Evidence grade A–E, separate from the truth score |
| looks at one video | **connects videos** through shared claims | Compare: shared claims, conflicts, same or independent sources |
| is a snapshot | shows **change over time** | "Insufficient Evidence → Verified" when new sources appear |
| says true or false | shows **which evidence each video relies on** | Source overlap, plus sources that support one video and refute another |

## Problem statement
Video is now where many people get their news, but nobody fact-checks it at the speed it spreads. A single clip can carry a dozen factual claims, from statistics and dates to health advice and quotes. Checking even one claim means pausing, searching, reading and comparing sources. Most viewers never do it, so they share what *sounds* right.

Existing fact-checks are written articles about selected viral claims, published hours or days later. They don't tell you, **while you're watching**, which of the statements in *this* video hold up.

And even when a claim *is* checked, the result is a one-off snapshot:
- **No memory.** The same claim resurfaces in video after video, reworded or with different numbers, and each one has to be checked from scratch.
- **No view of the evidence.** Viewers see a verdict, not how strong the evidence is or which sources it rests on.
- **No connections.** Nobody can easily see that two popular videos contradict each other, or that ten videos all lean on the same weak source.
- **No change over time.** When new evidence appears, old verdicts don't update and nobody is told.

> Tip: open with one recent, well-sourced statistic about video as a news source or about misinformation in your region, and cite it on the slide. Judges remember a number they can trust.

## Proposed solution
**LiveTruth Shield** works in two layers.

**Layer 1: Verify.** Any public video becomes an evidence-checked, timestamped report in minutes:
1. **Capture** the video from a link or an upload.
2. **Understand** the speech: transcribe it with timestamps and extract each checkable claim.
3. **Verify** each claim against evidence retrieved from trusted sources.
4. **Show** verdicts, sources and a colour-coded **truth timeline**. Click any segment to jump to that moment.

**Layer 2: Track.** Every analysed video receives a **Truth Fingerprint**, a permanent, versioned credibility record:
- a unique **LTS code**, plus a content hash that changes whenever the results change
- claim counts: verified, false, misleading, unverified
- an **evidence-quality grade** (A–E) showing how strong the support is, not just what the verdict is
- the **original timestamps** of every claim
- a **verification history** of every re-check and what changed

Any two fingerprints can be **compared** to find shared claims and see whether the videos rely on the same evidence, use different figures, or present conflicting information.

Layer 1 makes LiveTruth Shield a fact-checker. Layer 2 makes it a credibility and evidence-tracking platform.

## Innovation and uniqueness
- **From verdicts to credibility records**: each video gets a Truth Fingerprint that keeps its claims, evidence and verdicts over time, instead of a one-off answer.
- **Evidence quality as its own measure**: a video can be mostly false with grade-A evidence (we're sure it's wrong), or mostly verified with grade-D evidence (it looks right, but the support is thin).
- **Cross-video evidence tracking**: claims are matched by meaning across videos. The system shows whether two videos rest on the same sources, and flags the strongest conflict signal: one source that supports one video and refutes the other.
- **Verification history**: re-checks are versioned, so you can see when and why a verdict changed.
- **Claim-level, timestamped verification** of a whole video, rather than one viral claim at a time.
- **Evidence-gated verdicts**: the AI must quote the source passage verbatim. Quotes that don't exist are thrown out, and a verdict the evidence doesn't support is downgraded.
- **"Insufficient Evidence" as a first-class answer.** The system would rather say "we can't tell" than guess.
- **Computed, explainable confidence** from evidence volume, agreement, source diversity and credibility, never from the model's self-reported certainty.
- **Grounded claim extraction**: the model cites transcript segment ids and timestamps come from the transcript, so claims can't drift from what was actually said.
- **Provider-agnostic**: any OpenAI-compatible LLM, local or API Whisper, three search providers. It can run on-prem for newsrooms.

## Technical architecture (one-slide version)
React + Tailwind + Framer Motion + Recharts → FastAPI (REST, JWT) → async pipeline: yt-dlp/FFmpeg → Whisper → LLM claim extraction → search API → embeddings + ChromaDB (RAG) → LLM stance + evidence rules → MongoDB → Truth Fingerprint (versioned) → comparison engine (semantic claim matching + evidence overlap). Docker Compose deploys all of it.

## Implementation workflow
1. User submits link/file → API validates (allowlist, SSRF guard, size/type) → returns 202 instantly.
2. Background pipeline updates progress in MongoDB. The UI polls it and shows claims as they're verified.
3. Each claim: 2 searches → chunk → embed → retrieve top passages → stance judgement with quotes → grounding checks → verdict + confidence. The claim embedding is kept for cross-video matching.
4. Timeline + summary generated, results stored for history.
5. Truth Fingerprint recorded: a new version with its content hash and what changed since the last run.
6. Compare: claims matched by meaning across two fingerprints → verdict relation, figure differences, source overlap, opposite-stance sources.

## Real-world use cases
- **Everyday viewers**: check a viral clip before forwarding it to the family group.
- **Journalists and fact-checking desks**: triage a long speech or debate in minutes. See which videos repeat a debunked claim and whether they cite the same sources.
- **Researchers**: track how a claim's verdict and evidence change over time, and across channels.
- **Content moderators and platforms**: prioritise review queues, and spot clusters of videos built on the same weak evidence.
- **Educators**: teach media literacy by comparing two videos on the same topic, side by side, with visible evidence.
- **Election and public-health periods**: compare speeches and health-advice videos that make the same claims with different figures.

## Competitive advantages
| | Manual fact-checking | Generic AI chatbot | **LiveTruth Shield** |
|---|---|---|---|
| Whole-video coverage | ✗ (selected claims) | ✗ | ✓ every claim |
| Timestamps | ✗ | ✗ | ✓ click-to-seek |
| Cites evidence | ✓ | sometimes, unverifiable | ✓ verbatim, checked quotes |
| Admits uncertainty | ✓ | rarely | ✓ "Insufficient Evidence" |
| Speed | hours–days | seconds, ungrounded | minutes, grounded |
| Explainable confidence | n/a | ✗ | ✓ breakdown |
| Evidence-quality grade | ✗ | ✗ | ✓ A–E per video |
| Verification history | ✗ (article updates) | ✗ | ✓ versioned, with changes |
| Cross-video comparison | manual | ✗ | ✓ shared claims, conflicts, source overlap |

## Future enhancements
These turn the tracking layer into a full platform:
1. **Shared claim index**: "This claim appears in 14 analysed videos: 11 false, 3 misleading."
2. **Scheduled re-verification with alerts**: re-check fingerprints weekly and notify users when a verdict changes.
3. **Public fingerprint pages**: a shareable link or QR code for every LTS code.
4. **Claim-spread timeline**: when each video first made a claim, and how it travelled.
5. **Contradiction model (NLI)** to sharpen conflict detection between reworded claims.
6. **True live mode**: stream audio from live broadcasts in 30-second windows and update the timeline in real time.
7. **Browser extension** that shows a video's fingerprint and truth timeline on YouTube itself.
8. **Multilingual**: Whisper already transcribes Hindi, Telugu, Tamil and more. Add cross-lingual retrieval and translated explanations.
9. **Fact-check database matching** (Google Fact Check Tools API / ClaimReview), speaker diarisation, and OCR of on-screen text and charts.

---

## 10-slide deck content

**Slide 1 — Title**
LiveTruth Shield · *Video credibility and evidence tracking* · team name, members · tagline: *"Question information before believing or sharing it."*

**Slide 2 — The problem**
- Video spreads faster than fact-checks
- One clip = many claims; checking each takes minutes of searching
- Fact-checks are one-off snapshots: no memory, no view of the evidence, no connections between videos
- (one sourced statistic + citation)

**Slide 3 — From fact-checking to evidence tracking**
Two layers side by side:
- **Verify**: Capture → Understand → Verify → Show (truth timeline screenshot)
- **Track**: Truth Fingerprint → history → compare (fingerprint glyph)
One line under it: *"We don't just check a video. We keep a credibility record of it."*

**Slide 4 — Live demo**
(Switch to the app. See the demo script below.)

**Slide 5 — How it works**
Pipeline diagram: audio → Whisper → claim extraction → search → RAG retrieval → stance + evidence rules → verdict → Truth Fingerprint. Tech stack strip along the bottom: React · Tailwind · FastAPI · MongoDB · Whisper · LLM · ChromaDB · Tavily · Docker.

**Slide 6 — Why you can trust it**
- Verbatim quote check on every piece of evidence
- Verdicts gated by weighted evidence, with automatic downgrade
- Confidence computed from evidence, not AI self-belief
- "Insufficient Evidence" instead of guessing
- Small worked example: model said *verified*, sources disagreed → *misleading* (adjusted)

**Slide 7 — Truth Fingerprint & comparison**
Left: fingerprint glyph + LTS code, counts, evidence grade A–E, timestamps, version history.
Right: compare example: "Video A says the Great Wall is visible from the Moon; Video B says it isn't. The same source refutes A and supports B, so the videos state opposite things. Both cite Everest, with different figures."

**Slide 8 — Impact & use cases**
Viewers · journalists · researchers · moderators · educators, one line each, with the tracking angle ("see which videos repeat a debunked claim").

**Slide 9 — Competitive advantage**
Comparison table (above), with the three tracking rows highlighted.

**Slide 10 — Roadmap & close**
Shared claim index · scheduled re-verification alerts · public fingerprint pages · live mode · browser extension.
Closing line: *"Fact-checkers tell you if a video is wrong. LiveTruth Shield tells you how credible it is, what evidence it stands on, and where it contradicts the rest of the internet."*
Team contacts + repo link.

---

## Judge questions & answers

**Q: How do you stop the LLM from hallucinating verdicts?**
Three layers. (1) The model only sees retrieved passages and must quote one verbatim for every stance. We check the quote actually exists and discard it if it doesn't. (2) The verdict must be consistent with the weighted evidence. If the model says "verified" but the sources refute the claim, we downgrade it and show an "adjusted" flag. (3) With too little evidence, the answer is "Insufficient Evidence", never a guess.

**Q: Where does the confidence score come from?**
A formula over the grounded evidence: how much there is, how much it agrees, how many independent domains, and how credible they are. We never ask the model for a number. Each claim stores the breakdown, so the score is auditable.

**Q: Isn't "credible source" subjective?**
Yes, so we keep it transparent and editable: five tiers in one file (fact-checkers, official/scientific, established news, reference, general web), plus a blocklist for social media. It only weights evidence; it never decides a verdict alone. Next step is article-level signals and newsroom-configurable tiers.

**Q: Why is it called "Live" if it processes after upload?**
Today it analyses a full video in minutes and streams results into the UI as each claim finishes. The pipeline is chunk-based (10-minute audio chunks, windowed extraction), so true live mode means feeding 30-second windows from a stream. That's our first roadmap item.

**Q: What happens with claims nobody has written about?**
They come back "Insufficient Evidence". That's a feature: it tells the viewer the claim is unverified, which is exactly what they should know before sharing.

**Q: What is the Truth Fingerprint for?**
It's a compact, versioned record of a video's claims, verdicts and evidence quality, with a unique LTS code. The content hash changes whenever results change, and the history shows exactly which verdicts moved and when, e.g. a claim going from Insufficient Evidence to Verified once sources appear. It also enables comparison: two videos about the same topic can be matched claim by claim to see whether they rely on the same sources or contradict each other.

**Q: How do you know two videos make the "same" claim?**
We store each claim's embedding and match by meaning (cosine ≥ 0.82), with a wording-based fallback. We then compare verdicts, extract numbers to catch different figures, and measure source overlap. The strongest signal is when the same source supports one video's version and refutes the other's: the videos are stating opposite things.

**Q: How does it handle Telugu and Hindi videos?**
Whisper transcribes in the original script. Each claim is kept in the speaker's words with a faithful English translation for searching. We search in English and in the original language, and show results in English, Hindi or Telugu. Translations that change any number are rejected, and the verdict never depends on a translation.

**Q: Can it detect deepfakes?**
It runs media-authenticity signal checks (frame-timing gaps, audio splices, cuts that line up with audio breaks, lip-sync correlation, face consistency) and reports one of three outcomes: possible manipulation, no obvious indicators, or inconclusive. We deliberately never say "this is a deepfake", because these signals can't prove that and a high-quality fake can pass them. A trained classifier can plug into a dedicated hook, and its score would be shown separately.

**Q: How do you decide a source is trustworthy without just trusting big brands?**
Seven signals: publisher type, whether it's a primary source, named author, publication date, cited references, transparency, and independent corroboration. Corroboration (other independent sites agreeing) carries the most weight after publisher. An unknown blog that cites primary data and is corroborated can outscore a famous site that isn't. Every score shows its reasons.

**Q: What does the context detector catch that verdicts miss?**
A claim can be literally true and still misleading: a statistic from one district presented as national, or a quote with its "but" cut off. The detector compares each claim with the surrounding transcript and must quote the words that change the meaning, so it can't invent context. It also finds places where the speaker contradicts themselves.

**Q: What's in the PDF report, and why does it matter?**
Everything needed to audit the result: verdicts with timestamps, evidence links with trust levels, context flags, the Truth Fingerprint ID and version, and the limitations. Journalists and educators can attach it, and anyone can verify which version of the analysis they're looking at.

**Q: Isn't running all this expensive?**
Each run records its own timings, API calls, tokens and cache hits, and shows a cost estimate once you enter your provider prices. Evidence searches are cached, re-checks skip transcription, and local Whisper plus local embeddings can bring API costs close to zero.

**Q: How long does it take and what does it cost?**
Roughly 1–3 minutes for a 10-minute video with up to 25 claims. Cost is dominated by Whisper (per audio minute) plus about 2 searches and 1–2 small LLM calls per claim with `gpt-4o-mini`. Check current provider pricing for exact figures. A local Whisper and open-source LLM can bring API cost close to zero.

**Q: Is downloading videos legal?**
We only capture public content, with no logins, cookies or DRM circumvention. We keep audio only for transcription and delete it afterwards. Users are responsible for having the right to analyse what they submit, and deployments should follow each platform's terms. Uploads cover cases where a platform doesn't allow downloading.

**Q: How do you handle multiple languages?**
Whisper transcribes many languages including Indian ones, and the LLM can extract claims from them. Retrieval currently works best in English; cross-lingual retrieval is on the roadmap.

**Q: What if the transcript is wrong?**
We show the original quote next to every rewritten claim and let users jump to the exact second to hear it. Whisper is strong on clear speech. Names and numbers are the main risk.

**Q: Can this be gamed or biased?**
Any retrieval system reflects its sources. We mitigate this with source diversity in the confidence, the "mixed/misleading" outcome when sources disagree, and full evidence display so users judge for themselves. We position it as decision support, not an arbiter of truth.

**Q: How does it scale?**
The API is stateless and progress lives in MongoDB. The pipeline function takes only an id, so it moves straight into a job queue (Celery/Arq) with horizontal workers. Vector indexes are per analysis.

**Q: What did you build vs. use off the shelf?**
We used Whisper, the LLM, embeddings, ChromaDB and the search API. We built the grounding checks, the evidence-weighted verdict and confidence logic, claim extraction with segment anchoring, the pipeline, the API and the whole UI, plus tests covering the trust logic.

**Q: Isn't this just another fact-checker?**
Fact-checking is our first layer. The second layer is what makes it a platform: every video gets a Truth Fingerprint that keeps its claims, evidence grade and verification history, and fingerprints can be compared across videos. A fact-checker gives you a verdict. We give you a credibility record that connects to other videos and updates over time.

**Q: You say "tracking". Is it tracking across all users, and does it update automatically?**
Today, comparison works across your own analysed videos, and history grows each time an analysis is re-run. The engine is built: fingerprints, content hashes, semantic claim matching. Next come a shared claim index across users (a privacy and permissions decision) and scheduled re-verification with alerts when a verdict changes.

---

## 2-minute demo script

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | Landing page | "Video spreads faster than any fact-check, and fact-checks are one-off snapshots. LiveTruth Shield checks every claim in a video with evidence, and keeps a credibility record of it." |
| 0:15–0:30 | Dashboard → paste link → Start analysis | "I'll paste a public video link. It captures the audio, transcribes it with Whisper, and extracts each checkable claim with its timestamp." |
| 0:30–0:45 | Progress tracker, claims appearing | "Each claim is searched against trusted sources. The passages go into a vector index, and only the most relevant ones reach the model." |
| 0:45–1:05 | Completed analysis: summary + timeline | "Here's the result: an overall rating, and the truth timeline. Green is verified, red is false, yellow is misleading, grey means there wasn't enough evidence to decide." |
| 1:05–1:25 | Click a red segment → video jumps → claim card opens | "Click any segment and the video jumps to that second. This claim is false. Here's the explanation, and here's the exact sentence from the source that contradicts it." |
| 1:25–1:40 | Hover confidence, show 'Adjusted by evidence check' or a grey claim | "Confidence isn't the AI grading itself. It's computed from how much credible, independent evidence agrees. And when evidence is missing, we say so instead of guessing." |
| 1:40–1:55 | Truth Fingerprint card → Compare | "Every video gets a Truth Fingerprint. Compare two videos and you see the claims they share: here, one says the Great Wall is visible from the Moon and the other says it isn't, and the same source backs one and refutes the other." |
| 1:55–2:00 | Back to landing tagline | "LiveTruth Shield: from fact-checking to evidence tracking. Question information before believing or sharing it." |

**Demo safety net:** pre-run one analysis on the same video before you present (or run `scripts/seed_demo.py`) and keep that tab open, in case the venue Wi-Fi is slow. Start the live submission anyway and switch to the finished tab if needed.


---

## Existing system limitations
| Today's options | Limitation | LiveTruth Shield |
|---|---|---|
| Professional fact-checking sites | Selected viral claims only, hours to days later, articles not timestamps | Every claim in the video, minutes, clickable timestamps |
| Platform labels / community notes | Platform-specific, coarse (whole post), slow consensus | Claim-level verdicts on any public video or upload |
| General AI chatbots | Answer from memory, can't prove sources, rarely admit uncertainty | Retrieved evidence, verified quotes, "Insufficient Evidence" |
| Deepfake detectors | Single score, often overconfident, separate tool | Honest three-way outcome with reasons, next to the fact-check |
| English-first tools | Miss regional-language misinformation | Telugu, Hindi and English, with original-language search |

## Expected impact
- **Viewers:** a 30-second answer to "is this true?" before forwarding a clip, with sources they can read.
- **Newsrooms and fact-checkers:** triage long speeches and debates, jump to the questionable moments, and track whether the same claim spreads across videos.
- **Educators:** media-literacy lessons built on real videos, comparisons and visible evidence.
- **Platforms and researchers:** credibility records (fingerprints) that can be compared and re-checked over time.

---

## 2-minute project explanation (spoken)
> "Misinformation now spreads through video, in many languages, faster than anyone can fact-check it. LiveTruth Shield takes any public video or upload, transcribes the speech with Whisper in English, Hindi or Telugu, and pulls out every factual claim with its exact timestamp.
> For each claim we search trusted sources, retrieve the most relevant passages, and have the AI judge them, but the AI must quote the evidence word for word and we check that quote exists. The final verdict and confidence come from rules over the weighted evidence, not from the AI's opinion, and when the evidence isn't there we say 'Insufficient Evidence' instead of guessing.
> On top of that: a source trust analyser that explains why a source is trusted, a context detector for statements taken out of context, media-authenticity checks for signs of editing or manipulation, an evidence graph, and a PDF report.
> Every video gets a Truth Fingerprint, a versioned credibility record you can compare across videos to find shared, repeated or conflicting claims. From fact-checking to evidence tracking: verify before you believe, think before you share."

## 5-minute live demo script
| Time | Screen | Say / do |
|---|---|---|
| 0:00–0:30 | Landing page | Problem in one line. "Don't just watch videos, verify their truth." Point at the innovations strip. |
| 0:30–1:00 | Dashboard → paste a public link → Start | "Public videos or uploads. Unsupported or private links are rejected clearly." Show the progress stages. |
| 1:00–1:30 | Claims appearing live | "Each claim gets a code, a timestamp and its type. It's searched in English and the original language." |
| 1:30–2:15 | Completed: timeline + summary | Explain the four colours. Click a **red** segment → video jumps → open evidence → show the **verbatim quote** and the **trust badge** reasons. |
| 2:15–2:40 | A claim with a **context flag** | "True number, wrong framing: the next sentence limits it. The detector quotes the transcript to prove it." |
| 2:40–3:00 | Language switch → తెలుగు / हिन्दी | "Results in the viewer's language. Translations can't change a number." (Pre-run a Telugu or Hindi video if you have one.) |
| 3:00–3:30 | Fingerprint page → Compare | Seeded demo: Video A says the Great Wall is visible from the Moon, Video B says it isn't, and the same source refutes one and supports the other. |
| 3:30–4:00 | Evidence graph | Claims, sources, a source supporting one claim and refuting another, related claims in other videos. |
| 4:00–4:30 | Media authenticity (pre-run) | Three honest outcomes, the indicators with timestamps, and the limitations box. "We never say 'deepfake' on signals alone." |
| 4:30–5:00 | Download PDF report → close | Show the report briefly. Close with the tagline and the roadmap. |

**Safety net:** pre-run every analysis you'll show (`python -m scripts.seed_demo` plus your real demo videos) and keep tabs open. Record a backup screen video.
