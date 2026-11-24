import { VERDICTS } from '../../utils/format.js'

/**
 * A visual "fingerprint": unique per video and readable at a glance.
 *  - outer ring: one arc per claim, placed by its timestamp, coloured by verdict,
 *    thicker when the verdict's confidence is higher
 *  - inner ridges: derived from the content hash, so any change in claims, verdicts
 *    or evidence visibly changes the pattern
 *  - centre: evidence-quality grade
 */
export default function FingerprintGlyph({ fingerprint, size = 132 }) {
  const { timestamps = [], claims = [], content_hash = '', evidence_quality = {}, video = {} } = fingerprint
  const c = size / 2
  const rOuter = c - 8
  const total = Math.max(video.duration || 0, ...timestamps.map((t) => t.end), 1)
  const conf = Object.fromEntries(claims.map((x) => [x.claim_id, x.confidence]))

  const polar = (r, frac) => {
    const a = frac * 2 * Math.PI - Math.PI / 2
    return [c + r * Math.cos(a), c + r * Math.sin(a)]
  }
  const arc = (r, f0, f1) => {
    const [x0, y0] = polar(r, f0)
    const [x1, y1] = polar(r, f1)
    return `M ${x0} ${y0} A ${r} ${r} 0 ${f1 - f0 > 0.5 ? 1 : 0} 1 ${x1} ${y1}`
  }

  const hex = (content_hash || '0'.repeat(16)).padEnd(16, '0')
  const ridges = [0, 1, 2, 3].map((ring) => {
    const r = rOuter - 16 - ring * 8
    const segs = []
    for (let i = 0; i < 4; i++) {
      const n = parseInt(hex[ring * 4 + i], 16)
      const start = (i + (n % 4) / 16) / 4
      const len = 0.06 + (n / 15) * 0.16
      segs.push(<path key={i} d={arc(r, start, Math.min(start + len, start + 0.24))} stroke="#293f68"
        strokeOpacity={0.25 + ring * 0.15} strokeWidth={2.4} fill="none" strokeLinecap="round" />)
    }
    return <g key={ring}>{segs}</g>
  })

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img"
      aria-label={`Truth Fingerprint ${fingerprint.fingerprint_id}: ${timestamps.length} claims, evidence grade ${evidence_quality.grade}`}>
      <circle cx={c} cy={c} r={rOuter} fill="none" stroke="#e1e8f2" strokeWidth={8} />
      {timestamps.map((t) => {
        const f0 = t.start / total
        const f1 = Math.max(t.end / total, f0 + 0.012)
        const w = 4 + 6 * (conf[t.claim_id] ?? 0.2)
        return <path key={t.claim_id} d={arc(rOuter, f0, Math.min(f1, f0 + 0.98))} stroke={VERDICTS[t.verdict]?.color || VERDICTS.unverified.color}
          strokeWidth={w} fill="none" strokeLinecap="butt" />
      })}
      {ridges}
      <circle cx={c} cy={c} r={rOuter - 44} fill="#14213d" />
      <text x={c} y={c + 1} textAnchor="middle" dominantBaseline="middle" fill="#fff"
        style={{ font: `800 ${size / 9}px "Plus Jakarta Sans", sans-serif` }}>{evidence_quality.grade || '–'}</text>
    </svg>
  )
}
