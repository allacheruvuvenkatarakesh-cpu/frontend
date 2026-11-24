const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const lu = require("react-icons/lu");
const { applyTheme } = require("/root/.claude/skills/synced/57f5a6f5-d68c-4dd2-8733-ba9e7d75605a_6c89ca4d-46cf-401a-8a77-4cdfb1a887f1/pptx/scripts/apply_theme.js");

const THEME = {
  name: "LiveTruth Shield",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14213D", lt1: "FFFFFF", dk2: "42629B", lt2: "F1F4F9",
    accent1: "16A34A", accent2: "DC2626", accent3: "EAB308", accent4: "9CA3AF",
    accent5: "293F68", accent6: "C4D1E5", hlink: "324D80", folHlink: "6482B5",
  },
};
const HEX = { navy: "14213D", navy2: "293F68", muted: "42629B", tint: "F1F4F9", line: "C4D1E5",
  green: "16A34A", red: "DC2626", yellow: "EAB308", grey: "9CA3AF", white: "FFFFFF" };
const VERDICT = { verified: HEX.green, false: HEX.red, misleading: HEX.yellow, unverified: HEX.grey };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.title = "LiveTruth Shield — Hackathon Pitch";
pres.author = "LiveTruth Shield team";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------------------------------------------------------------- assets
async function iconPng(name, hex, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(lu[name], { size: px, color: "#" + hex, strokeWidth: 2 }));
  const buf = await sharp(Buffer.from(svg)).resize(px, px).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

function glyphSvg({ timestamps, duration, hash, grade, size = 600, dark = false }) {
  const c = size / 2, rOuter = c - 30;
  const polar = (r, f) => { const a = f * 2 * Math.PI - Math.PI / 2; return [c + r * Math.cos(a), c + r * Math.sin(a)]; };
  const arc = (r, f0, f1) => { const [x0, y0] = polar(r, f0), [x1, y1] = polar(r, f1);
    return `M ${x0} ${y0} A ${r} ${r} 0 ${f1 - f0 > 0.5 ? 1 : 0} 1 ${x1} ${y1}`; };
  const ring = dark ? "#293f68" : "#e1e8f2", ridge = dark ? "#c4d1e5" : "#293f68";
  let out = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">`;
  out += `<circle cx="${c}" cy="${c}" r="${rOuter}" fill="none" stroke="${ring}" stroke-width="34"/>`;
  for (const t of timestamps) {
    out += `<path d="${arc(rOuter, t.start / duration, Math.max(t.end / duration, t.start / duration + 0.015))}" stroke="#${VERDICT[t.verdict]}" stroke-width="${18 + 22 * (t.conf ?? 0.2)}" fill="none"/>`;
  }
  const hex = hash.padEnd(16, "0");
  for (let ring2 = 0; ring2 < 4; ring2++) {
    const r = rOuter - 70 - ring2 * 36;
    for (let i = 0; i < 4; i++) {
      const n = parseInt(hex[ring2 * 4 + i], 16), start = (i + (n % 4) / 16) / 4, len = 0.06 + (n / 15) * 0.16;
      out += `<path d="${arc(r, start, Math.min(start + len, start + 0.24))}" stroke="${ridge}" stroke-opacity="${0.3 + ring2 * 0.15}" stroke-width="11" fill="none" stroke-linecap="round"/>`;
    }
  }
  out += `<circle cx="${c}" cy="${c}" r="${rOuter - 196}" fill="${dark ? "#ffffff" : "#14213d"}"/>`;
  out += `<text x="${c}" y="${c + 28}" text-anchor="middle" font-family="Arial" font-weight="800" font-size="80" fill="${dark ? "#14213d" : "#ffffff"}">${grade}</text></svg>`;
  return out;
}
async function glyphPng(opts) {
  const buf = await sharp(Buffer.from(glyphSvg(opts))).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const shadow = () => ({ type: "outer", color: "14213D", opacity: 0.12, blur: 8, offset: 2, angle: 90 });

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "Title Dark",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 5.4, h: 1.0, fontSize: 44, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.6, w: 5.4, h: 0.5, fontSize: 20, color: C.accent6, margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "Content Light",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.7, fontSize: 32, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "LiveTruth Shield", options: { x: 0.5, y: 5.22, w: 3, h: 0.25, fontSize: 10, color: C.text2, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.25, fontSize: 10, color: C.text2, align: "right" },
});
pres.defineSlideMaster({
  title: "Content Dark",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.7, fontSize: 32, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "LiveTruth Shield", options: { x: 0.5, y: 5.22, w: 3, h: 0.25, fontSize: 10, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.25, fontSize: 10, color: C.accent6, align: "right" },
});

// ---------------------------------------------------------------- helpers
async function iconTile(slide, name, x, y, size, { bg = C.text1, iconHex = HEX.white, round = true, objectName } = {}) {
  slide.addShape(round ? pres.shapes.OVAL : pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w: size, h: size, fill: { color: bg }, line: { type: "none" }, rectRadius: round ? undefined : 0.12,
    objectName: (objectName || name) + " tile",
  });
  const pad = size * 0.24;
  slide.addImage({ data: await iconPng(name, iconHex), x: x + pad, y: y + pad, w: size - 2 * pad, h: size - 2 * pad,
    altText: name.replace(/^Lu/, "") + " icon", objectName: (objectName || name) + " icon" });
}

function card(slide, x, y, w, h, { fill = C.background1, objectName = "card", line = true } = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.1, fill: { color: fill }, objectName,
    line: line ? { color: HEX.line, width: 0.75 } : { type: "none" }, shadow: shadow(),
  });
}

function text(slide, str, opts) {
  slide.addText(str, { isTextBox: true, margin: 0, valign: "top", fontSize: 14, color: C.text1, ...opts });
}

function truthTimeline(slide, x, y, w, h, segs, objectName = "truth timeline") {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.05, fill: { color: C.background2 }, line: { type: "none" }, objectName: objectName + " track" });
  const total = segs.reduce((a, s) => a + s[1], 0);
  let cx = x;
  segs.forEach(([v, wt], i) => {
    const sw = (wt / total) * w;
    if (v) slide.addShape(pres.shapes.RECTANGLE, { x: cx + 0.02, y, w: Math.max(sw - 0.04, 0.05), h, fill: { color: VERDICT[v] }, line: { type: "none" }, objectName: `${objectName} ${i}` });
    cx += sw;
  });
}

// ---------------------------------------------------------------- build
(async () => {
  // ============ 1. Title
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "Title Dark", sectionTitle: "Opening" });
  s.addImage({ data: await iconPng("LuShieldCheck", HEX.white), x: 0.6, y: 0.75, w: 0.6, h: 0.6, altText: "Shield logo", objectName: "logo" });
  s.addText("LiveTruth Shield", { placeholder: "title" });
  s.addText("Video credibility and evidence tracking", { placeholder: "body" });
  text(s, "“Question information before believing or sharing it.”", { x: 0.6, y: 3.3, w: 5.4, h: 0.4, fontSize: 16, italic: true, color: C.background1 });
  text(s, "[Team name]  ·  [Member names]  ·  [Hackathon name, date]", { x: 0.6, y: 4.6, w: 5.4, h: 0.3, fontSize: 12, color: C.accent6 });
  s.addImage({ data: await glyphPng({ timestamps: [
      { start: 10.8, end: 17.5, verdict: "false", conf: 0.86 }, { start: 17.5, end: 23.9, verdict: "verified", conf: 0.82 },
      { start: 23.9, end: 30.1, verdict: "false", conf: 0.84 }, { start: 30.1, end: 36.4, verdict: "misleading", conf: 0.61 },
      { start: 41.0, end: 47.6, verdict: "unverified" }],
    duration: 52, hash: "8cc3281ed9102187", grade: "B", dark: true }),
    x: 6.55, y: 1.15, w: 3.0, h: 3.0, altText: "Truth Fingerprint emblem: coloured arcs for each claim's verdict around a grade", objectName: "fingerprint emblem" });
  text(s, "LTS-FC2D-EF48-490D", { x: 6.55, y: 4.3, w: 3.0, h: 0.3, fontSize: 12, color: C.accent6, align: "center", fontFace: "Courier New" });
  s.addNotes("Introduce the team. One line: LiveTruth Shield checks every factual claim in a video against real evidence, and keeps a credibility record of every video it checks. The emblem on the right is a Truth Fingerprint; we'll come back to it.");

  // ============ 2. Problem
  pres.addSection({ title: "Problem & solution" });
  s = pres.addSlide({ masterName: "Content Light", sectionTitle: "Problem & solution" });
  s.addText("Video spreads faster than any fact-check", { placeholder: "title" });
  const problems = [
    ["LuZap", "Too fast", "A clip reaches thousands before anyone checks it."],
    ["LuMessageSquareQuote", "Too many claims", "One video can hold a dozen statistics, dates and quotes."],
    ["LuHourglass", "Too slow to check", "Each claim means pausing, searching and comparing sources."],
    ["LuUnlink", "No memory", "Fact-checks are one-off snapshots, not linked across videos."],
  ];
  for (let i = 0; i < problems.length; i++) {
    const [ic, h, d] = problems[i], y = 1.25 + i * 0.95;
    await iconTile(s, ic, 0.5, y, 0.6, { objectName: `problem ${i + 1}` });
    text(s, h, { x: 1.3, y: y + 0.02, w: 4.3, h: 0.3, fontSize: 16, bold: true });
    text(s, d, { x: 1.3, y: y + 0.33, w: 4.3, h: 0.3, fontSize: 14, color: C.text2 });
  }
  card(s, 6.0, 1.25, 3.5, 3.55, { fill: C.background2, line: false, objectName: "statistic card" });
  text(s, "Add one sourced statistic", { x: 6.3, y: 1.55, w: 2.9, h: 0.35, fontSize: 14, bold: true, color: C.text2 });
  text(s, "[ 00% ]", { x: 6.3, y: 2.0, w: 2.9, h: 1.0, fontSize: 54, bold: true, color: C.text1 });
  text(s, "e.g. share of people in your region who get news from online video", { x: 6.3, y: 3.1, w: 2.9, h: 0.8, fontSize: 14, color: C.text1 });
  text(s, "Source: [publisher, year]", { x: 6.3, y: 4.25, w: 2.9, h: 0.3, fontSize: 11, italic: true, color: C.text2 });
  s.addNotes("Replace the statistic placeholder with one real, cited figure before presenting. Then: video spreads faster than fact-checks; one clip holds many claims; checking each takes minutes; and today's fact-checks are one-off snapshots with no memory, no view of the evidence, and no connections between videos.");

  // ============ 3. Solution: two layers
  s = pres.addSlide({ masterName: "Content Light", sectionTitle: "Problem & solution" });
  s.addText("From fact-checking to evidence tracking", { placeholder: "title" });
  // Layer 1
  card(s, 0.5, 1.2, 4.35, 3.35, { objectName: "layer 1 card" });
  text(s, "LAYER 1  ·  VERIFY", { x: 0.75, y: 1.4, w: 3.9, h: 0.3, fontSize: 12, bold: true, color: C.text2, charSpacing: 2 });
  const steps = [["LuLink", "Capture", "link or upload"], ["LuAudioLines", "Understand", "speech → claims"], ["LuFileSearch", "Verify", "against evidence"], ["LuListChecks", "Show", "verdict timeline"]];
  for (let i = 0; i < 4; i++) {
    const [ic, h, d] = steps[i], x = 0.75 + i * 1.0;
    await iconTile(s, ic, x + 0.15, 1.85, 0.55, { objectName: `verify step ${i + 1}` });
    text(s, h, { x, y: 2.5, w: 0.9, h: 0.28, fontSize: 13, bold: true, align: "center" });
    text(s, d, { x: x - 0.05, y: 2.78, w: 1.0, h: 0.45, fontSize: 11, color: C.text2, align: "center" });
  }
  truthTimeline(s, 0.75, 3.55, 3.85, 0.22, [[null, 10.8], ["false", 6.7], ["verified", 6.4], ["false", 6.2], ["misleading", 6.3], [null, 4.6], ["unverified", 6.6], [null, 4.4]], "layer 1 timeline");
  text(s, "Colour-coded truth timeline: click any segment to jump to that second", { x: 0.75, y: 3.9, w: 3.85, h: 0.45, fontSize: 11, color: C.text2 });
  // arrow
  s.addImage({ data: await iconPng("LuArrowRight", HEX.muted), x: 4.92, y: 2.6, w: 0.36, h: 0.36, altText: "arrow", objectName: "layer arrow" });
  // Layer 2
  card(s, 5.35, 1.2, 4.15, 3.35, { fill: C.text1, line: false, objectName: "layer 2 card" });
  text(s, "LAYER 2  ·  TRACK", { x: 5.6, y: 1.4, w: 3.7, h: 0.3, fontSize: 12, bold: true, color: C.accent6, charSpacing: 2 });
  const track = [["LuFingerprint", "Truth Fingerprint", "unique credibility record per video"], ["LuHistory", "Verification history", "every re-check versioned"], ["LuGitCompare", "Compare videos", "shared claims, conflicts, sources"]];
  for (let i = 0; i < 3; i++) {
    const [ic, h, d] = track[i], y = 1.85 + i * 0.85;
    await iconTile(s, ic, 5.6, y, 0.55, { bg: C.background1, iconHex: HEX.navy, objectName: `track ${i + 1}` });
    text(s, h, { x: 6.3, y: y + 0.02, w: 3.0, h: 0.28, fontSize: 14, bold: true, color: C.background1 });
    text(s, d, { x: 6.3, y: y + 0.3, w: 3.0, h: 0.28, fontSize: 12, color: C.accent6 });
  }
  text(s, "We don't just check a video. We keep a credibility record of it.", { x: 0.5, y: 4.7, w: 9.0, h: 0.35, fontSize: 16, italic: true, bold: true, color: C.text1, align: "center" });
  s.addNotes("Two layers. Layer 1 makes it a fact-checker: capture, understand, verify, show. Layer 2 makes it a credibility and evidence-tracking platform: every video gets a Truth Fingerprint, every re-check is versioned, and any two videos can be compared.");

  // ============ 4. Demo
  pres.addSection({ title: "Product" });
  s = pres.addSlide({ masterName: "Content Dark", sectionTitle: "Product" });
  s.addText("Live demo", { placeholder: "title" });
  // mock analysis screen
  card(s, 0.5, 1.2, 5.6, 3.75, { fill: C.background1, line: false, objectName: "app mockup" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 1.4, w: 2.9, h: 1.6, rectRadius: 0.08, fill: { color: C.accent5 }, line: { type: "none" }, objectName: "mock video" });
  s.addImage({ data: await iconPng("LuPlay", HEX.white), x: 1.9, y: 1.95, w: 0.5, h: 0.5, altText: "play", objectName: "mock play" });
  text(s, "Overall", { x: 3.8, y: 1.45, w: 2.1, h: 0.25, fontSize: 11, color: C.text2 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.8, y: 1.72, w: 1.6, h: 0.32, rectRadius: 0.16, fill: { color: "FEE2E2" }, line: { color: HEX.red, width: 0.75 }, objectName: "mock rating" });
  text(s, "Mostly Inaccurate", { x: 3.8, y: 1.72, w: 1.6, h: 0.32, fontSize: 11, bold: true, align: "center", valign: "middle", color: "991B1B" });
  text(s, "Truth score", { x: 3.8, y: 2.2, w: 2.1, h: 0.25, fontSize: 11, color: C.text2 });
  text(s, "36", { x: 3.8, y: 2.42, w: 2.1, h: 0.55, fontSize: 32, bold: true });
  truthTimeline(s, 0.7, 3.2, 5.2, 0.26, [[null, 10.8], ["false", 6.7], ["verified", 6.4], ["false", 6.2], ["misleading", 6.3], [null, 4.6], ["unverified", 6.6], [null, 4.4]], "demo timeline");
  const mockClaims = [["false", "0:10", "Great Wall is visible from the Moon"], ["verified", "0:17", "Everest is the highest mountain"], ["misleading", "0:30", "Napoleon was much shorter than average"]];
  mockClaims.forEach(([v, t, c], i) => {
    const y = 3.65 + i * 0.4;
    s.addShape(pres.shapes.OVAL, { x: 0.75, y: y + 0.09, w: 0.14, h: 0.14, fill: { color: VERDICT[v] }, line: { type: "none" }, objectName: `mock claim dot ${i}` });
    text(s, [{ text: t + "  ", options: { fontFace: "Courier New", color: C.text2 } }, { text: c }], { x: 1.0, y, w: 4.9, h: 0.32, fontSize: 12, valign: "middle" });
  });
  // demo flow
  const flow = ["Paste a public video link", "Watch claims appear as they're verified", "Click a red segment: video jumps there", "Open the evidence and its exact quote", "Show the Truth Fingerprint, then Compare"];
  flow.forEach((f, i) => {
    const y = 1.25 + i * 0.75;
    s.addShape(pres.shapes.OVAL, { x: 6.5, y, w: 0.45, h: 0.45, fill: { color: C.background1 }, line: { type: "none" }, objectName: `demo step ${i + 1}` });
    text(s, String(i + 1), { x: 6.5, y, w: 0.45, h: 0.45, fontSize: 16, bold: true, align: "center", valign: "middle" });
    text(s, f, { x: 7.1, y: y - 0.02, w: 2.4, h: 0.5, fontSize: 13, color: C.background1, valign: "middle" });
  });
  s.addNotes("Switch to the app. 0:15 paste link and start. 0:30 progress and claims appearing. 0:45 summary and truth timeline: green verified, red false, yellow misleading, grey insufficient evidence. 1:05 click a red segment, the video jumps, show the explanation and the exact source sentence. 1:25 confidence is computed from evidence, not the AI. 1:40 Truth Fingerprint card, then Compare: one video says the Great Wall is visible from the Moon, the other says it isn't; the same source backs one and refutes the other. Safety net: keep a pre-run analysis open in another tab.");

  // ============ 5. How it works
  s = pres.addSlide({ masterName: "Content Light", sectionTitle: "Product" });
  s.addText("How it works", { placeholder: "title" });
  const pipe = [["LuAudioLines", "Whisper", "speech → timed segments"], ["LuBrainCircuit", "Claim extraction", "LLM, grounded to segments"], ["LuSearch", "Evidence search", "web + fact-check queries"],
    ["LuDatabase", "RAG retrieval", "embeddings + ChromaDB"], ["LuScale", "Verdict rules", "quotes checked, evidence weighted"], ["LuFingerprint", "Fingerprint", "versioned record + compare"]];
  const pw = 1.35, gap = 0.18;
  for (let i = 0; i < pipe.length; i++) {
    const [ic, h, d] = pipe[i], x = 0.5 + i * (pw + gap);
    card(s, x, 1.3, pw, 2.2, { objectName: `pipeline ${i + 1}` });
    await iconTile(s, ic, x + (pw - 0.6) / 2, 1.5, 0.6, { objectName: `pipeline icon ${i + 1}` });
    text(s, h, { x: x + 0.08, y: 2.25, w: pw - 0.16, h: 0.5, fontSize: 13, bold: true, align: "center", valign: "middle" });
    text(s, d, { x: x + 0.08, y: 2.75, w: pw - 0.16, h: 0.6, fontSize: 11, color: C.text2, align: "center" });
  }
  card(s, 0.5, 3.8, 9.0, 1.15, { fill: C.background2, line: false, objectName: "stack card" });
  const stack = [["Frontend", "React · Tailwind · Framer Motion · Recharts"], ["Backend", "FastAPI · JWT · MongoDB · Docker"], ["AI", "Whisper · OpenAI-compatible LLM · ChromaDB · Tavily"]];
  stack.forEach(([h, d], i) => {
    const x = 0.75 + i * 2.95;
    text(s, h.toUpperCase(), { x, y: 3.98, w: 2.75, h: 0.25, fontSize: 11, bold: true, color: C.text2, charSpacing: 1 });
    text(s, d, { x, y: 4.25, w: 2.75, h: 0.55, fontSize: 13 });
  });
  s.addNotes("Audio goes through Whisper into timestamped segments. The LLM extracts claims and points to segment numbers, so timestamps always come from the transcript. Each claim gets two web searches, passages are embedded and retrieved by meaning, and the AI judges each passage with a verbatim quote. Rules over the weighted evidence decide the verdict, and every run is saved as a Truth Fingerprint version.");

  // ============ 6. Trust
  pres.addSection({ title: "Differentiation" });
  s = pres.addSlide({ masterName: "Content Light", sectionTitle: "Differentiation" });
  s.addText("Why you can trust it", { placeholder: "title" });
  const trust = [["LuQuote", "Quotes are checked", "The AI must quote each source word for word. Quotes that don't exist are thrown out."],
    ["LuScale", "Evidence decides", "A verdict the weighted evidence doesn't support is downgraded automatically."],
    ["LuGauge", "Confidence is computed", "From how much credible, independent evidence agrees, never the AI's self-belief."],
    ["LuCircleHelp", "No guessing", "Not enough evidence? The answer is “Insufficient Evidence”."]];
  for (let i = 0; i < 4; i++) {
    const [ic, h, d] = trust[i], col = i % 2, row = Math.floor(i / 2), x = 0.5 + col * 2.85, y = 1.2 + row * 1.85;
    card(s, x, y, 2.65, 1.65, { objectName: `trust card ${i + 1}` });
    await iconTile(s, ic, x + 0.2, y + 0.2, 0.5, { objectName: `trust icon ${i + 1}` });
    text(s, h, { x: x + 0.82, y: y + 0.25, w: 1.7, h: 0.45, fontSize: 14, bold: true, valign: "middle" });
    text(s, d, { x: x + 0.2, y: y + 0.82, w: 2.3, h: 0.75, fontSize: 12, color: C.text2 });
  }
  card(s, 6.3, 1.2, 3.2, 3.5, { fill: C.text1, line: false, objectName: "worked example" });
  text(s, "WORKED EXAMPLE", { x: 6.55, y: 1.4, w: 2.8, h: 0.25, fontSize: 11, bold: true, color: C.accent6, charSpacing: 2 });
  const ex = [["AI suggests", "Verified", HEX.green], ["Evidence found", "1 source supports, 1 refutes", null], ["Final verdict", "Misleading", HEX.yellow]];
  ex.forEach(([lab, val, col], i) => {
    const y = 1.8 + i * 0.78;
    text(s, lab, { x: 6.55, y, w: 2.8, h: 0.25, fontSize: 11, color: C.accent6 });
    if (col) {
      s.addShape(pres.shapes.OVAL, { x: 6.55, y: y + 0.36, w: 0.16, h: 0.16, fill: { color: col }, line: { type: "none" }, objectName: `example dot ${i}` });
      text(s, val, { x: 6.8, y: y + 0.27, w: 2.5, h: 0.35, fontSize: 16, bold: true, color: C.background1, valign: "middle" });
    } else {
      text(s, val, { x: 6.55, y: y + 0.27, w: 2.8, h: 0.35, fontSize: 14, color: C.background1, valign: "middle" });
    }
  });
  text(s, "Marked “Adjusted by evidence check” so users see why", { x: 6.55, y: 4.15, w: 2.8, h: 0.45, fontSize: 11, italic: true, color: C.accent6 });
  s.addNotes("This is what separates us from asking a chatbot. Every stance needs a verbatim quote, and we verify it exists. The final verdict must match the weighted evidence; here the AI said verified, but sources disagreed, so the result is misleading, and the card says it was adjusted. Confidence is a formula over the evidence. With no evidence, we say Insufficient Evidence.");

  // ============ 7. Fingerprint & compare
  s = pres.addSlide({ masterName: "Content Light", sectionTitle: "Differentiation" });
  s.addText("Truth Fingerprint & video comparison", { placeholder: "title" });
  card(s, 0.5, 1.2, 4.2, 3.75, { objectName: "fingerprint card" });
  s.addImage({ data: await glyphPng({ timestamps: [
      { start: 10.8, end: 17.5, verdict: "false", conf: 0.86 }, { start: 17.5, end: 23.9, verdict: "verified", conf: 0.82 },
      { start: 23.9, end: 30.1, verdict: "false", conf: 0.84 }, { start: 30.1, end: 36.4, verdict: "misleading", conf: 0.61 },
      { start: 41.0, end: 47.6, verdict: "unverified" }],
    duration: 52, hash: "8cc3281ed9102187", grade: "B" }), x: 0.75, y: 1.45, w: 1.7, h: 1.7, altText: "Truth Fingerprint emblem", objectName: "fingerprint glyph" });
  text(s, "LTS-FC2D-EF48-490D", { x: 2.6, y: 1.5, w: 2.0, h: 0.28, fontSize: 11, fontFace: "Courier New", color: C.text2 });
  text(s, "5 claims", { x: 2.6, y: 1.8, w: 2.0, h: 0.4, fontSize: 22, bold: true });
  const counts = [["verified", "1 verified"], ["false", "2 false"], ["misleading", "1 misleading"], ["unverified", "1 insufficient"]];
  counts.forEach(([v, lab], i) => {
    const y = 2.25 + i * 0.24;
    s.addShape(pres.shapes.OVAL, { x: 2.6, y: y + 0.06, w: 0.12, h: 0.12, fill: { color: VERDICT[v] }, line: { type: "none" }, objectName: `count dot ${v}` });
    text(s, lab, { x: 2.8, y, w: 1.8, h: 0.24, fontSize: 12, valign: "middle" });
  });
  const fpRows = [["Evidence quality", "Grade B · Good · 67/100"], ["Timestamps", "0:10 · 0:17 · 0:23 · 0:30 · 0:41"], ["History", "v1 · hash 8cc3281ed9102187"]];
  fpRows.forEach(([h, d], i) => {
    const y = 3.35 + i * 0.5;
    text(s, h, { x: 0.75, y, w: 1.4, h: 0.4, fontSize: 12, bold: true });
    text(s, d, { x: 2.15, y, w: 2.4, h: 0.45, fontSize: 12, color: C.text2 });
  });
  // comparison
  text(s, "Compare: Video A vs Video B", { x: 5.0, y: 1.2, w: 4.5, h: 0.35, fontSize: 16, bold: true });
  text(s, "3 shared claims · 2 consistent · 1 conflicting", { x: 5.0, y: 1.55, w: 4.5, h: 0.3, fontSize: 12, color: C.text2 });
  const cmp = [
    [HEX.red, "FEE2E2", "991B1B", "Conflicting", "Great Wall visible from the Moon?", "A: False · B: Verified. The same source refutes A and supports B."],
    [HEX.yellow, "FEF9C3", "854D0E", "Different figures", "Everest's height", "Both verified, same source: 8,849 m vs 8,848 m."],
    [HEX.green, "DCFCE7", "166534", "Consistent", "“We use 10% of our brains”", "False in both, backed by the same evidence."],
  ];
  cmp.forEach(([border, fill, ink, label, claimT, detail], i) => {
    const y = 2.0 + i * 1.0;
    card(s, 5.0, y, 4.5, 0.88, { objectName: `compare row ${i + 1}` });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.15, y: y + 0.14, w: 1.35, h: 0.28, rectRadius: 0.14, fill: { color: fill }, line: { color: border, width: 0.75 }, objectName: `relation chip ${i + 1}` });
    text(s, label, { x: 5.15, y: y + 0.14, w: 1.35, h: 0.28, fontSize: 10, bold: true, color: ink, align: "center", valign: "middle" });
    text(s, claimT, { x: 6.65, y: y + 0.12, w: 2.75, h: 0.32, fontSize: 12, bold: true, valign: "middle" });
    text(s, detail, { x: 5.15, y: y + 0.48, w: 4.25, h: 0.35, fontSize: 11, color: C.text2 });
  });
  s.addNotes("Every analysed video gets a Truth Fingerprint: a unique LTS code, claim counts, an evidence-quality grade, original timestamps, and a verification history showing what changed on each re-check. Compare two videos: claims are matched by meaning, then we compare verdicts, figures and sources. The strongest signal: the same source supports one video and refutes the other, so they're stating opposite things.");

  // ============ 8. Impact
  pres.addSection({ title: "Impact" });
  s = pres.addSlide({ masterName: "Content Light", sectionTitle: "Impact" });
  s.addText("Who it helps", { placeholder: "title" });
  const users = [["LuEye", "Everyday viewers", "Check a viral clip before forwarding it to the family group."],
    ["LuNewspaper", "Journalists", "Triage a long speech in minutes; see which videos repeat a debunked claim."],
    ["LuMicroscope", "Researchers", "Track how a claim's verdict and evidence change over time."],
    ["LuShield", "Moderators", "Spot clusters of videos built on the same weak evidence."],
    ["LuGraduationCap", "Educators", "Teach media literacy by comparing two videos side by side."],
    ["LuVote", "Elections & health", "Compare speeches and advice videos using different figures."]];
  for (let i = 0; i < users.length; i++) {
    const [ic, h, d] = users[i], col = i % 3, row = Math.floor(i / 3), x = 0.5 + col * 3.07, y = 1.2 + row * 1.9;
    card(s, x, y, 2.86, 1.7, { objectName: `user card ${i + 1}` });
    await iconTile(s, ic, x + 0.2, y + 0.2, 0.5, { objectName: `user icon ${i + 1}` });
    text(s, h, { x: x + 0.85, y: y + 0.22, w: 1.9, h: 0.45, fontSize: 15, bold: true, valign: "middle" });
    text(s, d, { x: x + 0.2, y: y + 0.85, w: 2.5, h: 0.75, fontSize: 12, color: C.text2 });
  }
  s.addNotes("Pick two or three of these that fit your judges. For a journalism or civic-tech panel, lead with journalists and moderators and the tracking angle: which videos repeat a debunked claim, and whether they rely on the same weak sources.");

  // ============ 9. Competitive advantage
  s = pres.addSlide({ masterName: "Content Light", sectionTitle: "Impact" });
  s.addText("What makes it different", { placeholder: "title" });
  const yes = { text: "✓", options: { color: C.accent1, bold: true } };
  const no = { text: "✗", options: { color: C.accent2, bold: true } };
  const head = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 } } });
  const ours = (t) => ({ text: t, options: { bold: true, fill: { color: C.background2 } } });
  const rows = [
    [head(""), head("Manual fact-checks"), head("AI chatbot"), head("LiveTruth Shield")],
    ["Whole-video coverage", "Selected claims", no, ours("✓ every claim")],
    ["Clickable timestamps", no, no, ours("✓ click-to-seek")],
    ["Checked evidence quotes", yes, "Unverifiable", ours("✓ verified quotes")],
    ["Admits uncertainty", yes, "Rarely", ours("✓ Insufficient Evidence")],
    ["Speed", "Hours to days", "Seconds, ungrounded", ours("Minutes, grounded")],
    [{ text: "Evidence-quality grade", options: { bold: true } }, no, no, ours("✓ A–E per video")],
    [{ text: "Verification history", options: { bold: true } }, "Article updates", no, ours("✓ versioned")],
    [{ text: "Cross-video comparison", options: { bold: true } }, "Manual", no, ours("✓ conflicts & sources")],
  ];
  s.addTable(rows, { x: 0.5, y: 1.2, w: 9.0, colW: [2.5, 2.0, 2.0, 2.5], fontSize: 12, color: C.text1, valign: "middle",
    rowH: 0.38, border: { type: "solid", color: HEX.line, pt: 0.75 }, margin: [0, 0.1, 0, 0.1], objectName: "comparison table" });
  text(s, "Bold rows: the evidence-tracking layer no fact-checker or chatbot offers", { x: 0.5, y: 4.75, w: 9.0, h: 0.3, fontSize: 11, italic: true, color: C.text2 });
  s.addNotes("Walk the bottom three rows: evidence-quality grade, verification history, cross-video comparison. That's the evidence-tracking layer. Manual fact-checks are thorough but slow and selective; chatbots are fast but answer from memory and can't prove where their answer came from.");

  // ============ 10. Roadmap & close
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "Content Dark", sectionTitle: "Close" });
  s.addText("Roadmap", { placeholder: "title" });
  const road = [["LuLayers", "Shared claim index", "every video that makes a claim"], ["LuBell", "Re-check alerts", "notify when a verdict changes"],
    ["LuGlobe", "Public fingerprints", "shareable link or QR code"], ["LuRadio", "Live mode", "30-second streaming windows"], ["LuRepeat", "Browser extension", "fingerprint on YouTube itself"]];
  for (let i = 0; i < road.length; i++) {
    const [ic, h, d] = road[i], x = 0.5 + i * 1.84;
    await iconTile(s, ic, x + 0.55, 1.25, 0.6, { bg: C.background1, iconHex: HEX.navy, objectName: `roadmap ${i + 1}` });
    text(s, h, { x, y: 1.98, w: 1.7, h: 0.3, fontSize: 13, bold: true, color: C.background1, align: "center" });
    text(s, d, { x, y: 2.28, w: 1.7, h: 0.5, fontSize: 11, color: C.accent6, align: "center" });
  }
  text(s, "“Fact-checkers tell you if a video is wrong. LiveTruth Shield tells you how credible it is, what evidence it stands on, and where it contradicts the rest of the internet.”",
    { x: 1.0, y: 3.1, w: 8.0, h: 1.0, fontSize: 18, italic: true, bold: true, color: C.background1, align: "center", valign: "middle" });
  text(s, "[Team contacts]  ·  [Repo / demo link]", { x: 1.0, y: 4.4, w: 8.0, h: 0.3, fontSize: 12, color: C.accent6, align: "center" });
  s.addNotes("Roadmap items complete the platform: a shared claim index across users, scheduled re-verification with alerts, public fingerprint pages, true live mode, and a browser extension. Close with the quote, then: LiveTruth Shield, from fact-checking to evidence tracking. Question information before believing or sharing it.");

  await pres.writeFile({ fileName: "LiveTruth_Shield_Pitch.pptx" });
  await applyTheme("LiveTruth_Shield_Pitch.pptx", THEME);
  console.log("written");
})().catch((e) => { console.error(e); process.exit(1); });
