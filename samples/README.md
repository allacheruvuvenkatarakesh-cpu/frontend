# Sample inputs and error scenarios

## Sample transcript
`backend/tests/fixtures/sample_transcript.json` is a synthetic 52-second "facts you learned in school" transcript. It mixes:

| Segment | Statement | Expected outcome |
|---|---|---|
| 2 | Great Wall visible from the Moon | **False** |
| 3 | Everest highest above sea level, ~8,849 m | **Verified** |
| 4 | Humans use only 10% of their brains | **False** |
| 5 | Napoleon much shorter than average | **Misleading** |
| 6 | "Makes history more fun" | Not extracted (opinion) |
| 7 | Water boils at 100 °C at sea level | **Verified** if evidence is found, otherwise **Insufficient Evidence** |
| 0, 1, 8 | Greetings, call to action | Not extracted |

It's used by the Pytest pipeline test and by `scripts/seed_demo.py`.

## Making a test video from the sample transcript
To test uploads end to end without downloading anything, record yourself (or use any text-to-speech tool) reading `sample_script.txt`, save as MP4 or MP3, and upload it. A 1-minute clip finishes in well under a minute.

## Choosing demo videos
Pick **public** videos you have the right to analyse, ideally 2–6 minutes long with clear speech and several specific factual statements, such as:
- a short explainer or "myths debunked" video
- a news segment with statistics
- a public speech or press briefing clip

Avoid music videos (little speech), private or age-restricted videos (rejected by design), and live streams that are still running.

## Error scenarios to demo or test

| Scenario | How to trigger | Expected behaviour |
|---|---|---|
| Unsupported link | `https://example.com/article` | 422 `unsupported_source`, form shows message |
| Look-alike domain | `https://notyoutube.com/watch?v=x` | 422, not treated as YouTube |
| Private network URL (SSRF) | `http://127.0.0.1/a.mp4` | 422, blocked |
| Bad file type | upload `notes.pdf` | 422 before upload is stored |
| Too large | file > `MAX_UPLOAD_MB` | rejected client-side and server-side |
| No audio track | silent screen recording | analysis **failed**: "This video has no audio track" |
| No speech | instrumental music | analysis **failed**: "No speech was detected" |
| Private / sign-in video | private YouTube link | analysis **failed** with a clear reason |
| Too long | video > `MAX_VIDEO_MINUTES` | analysis **failed** with the limit |
| Missing API key | blank `OPENAI_API_KEY` | analysis **failed**: service not configured |
| No evidence found | obscure local claim | claim marked **Insufficient Evidence**, never guessed |
| Server restart mid-analysis | restart backend | marked failed on startup; **Retry** works |
| Expired login | wait past `JWT_EXPIRE_MINUTES` | 401 → frontend signs out and returns to login |
| Rate limit | > 10 submissions/hour | 429 with retry time |
