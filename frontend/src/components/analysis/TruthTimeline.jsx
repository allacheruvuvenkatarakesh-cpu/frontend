import { motion } from 'framer-motion'
import { useState } from 'react'
import { formatTime, VERDICTS } from '../../utils/format.js'

/** Colour-coded bar across the video's duration. Each claim is a clickable segment. */
export default function TruthTimeline({ items, duration, selectedId, currentTime, onSelect }) {
  const [hover, setHover] = useState(null)
  const total = Math.max(duration || 0, ...items.map((i) => i.end), 1)
  const minWidth = 0.9 // % so very short claims stay clickable

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-bold">Truth timeline</h2>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-navy-600">
          {Object.entries(VERDICTS).map(([k, m]) => (
            <li key={k} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: m.color }} />{m.label}</li>
          ))}
        </ul>
      </div>

      <div className="relative mt-5">
        <div className="relative h-9 w-full rounded-lg bg-navy-50 ring-1 ring-navy-100 overflow-visible" role="list" aria-label="Claims along the video timeline">
          {items.map((it, i) => {
            const left = (it.start / total) * 100
            const width = Math.max(((it.end - it.start) / total) * 100, minWidth)
            const sel = it.claim_id === selectedId
            return (
              <motion.button key={it.claim_id} role="listitem"
                initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ delay: i * 0.03 }}
                onClick={() => onSelect(it)} onMouseEnter={() => setHover(it)} onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(it)} onBlur={() => setHover(null)}
                aria-label={`${formatTime(it.start)} — ${it.label}: ${it.text}`}
                className={`absolute top-0 h-full rounded-md transition-shadow ${sel ? 'ring-2 ring-navy-900 ring-offset-2 z-10' : 'hover:brightness-110'}`}
                style={{ left: `${Math.min(left, 100 - width)}%`, width: `${width}%`, background: it.color }} />
            )
          })}
          {currentTime != null && currentTime > 0 && (
            <div className="pointer-events-none absolute -top-1 -bottom-1 w-0.5 bg-navy-900" style={{ left: `${Math.min((currentTime / total) * 100, 100)}%` }} />
          )}
        </div>
        {hover && (
          <div className="pointer-events-none absolute z-20 mt-2 w-72 -translate-x-1/2 rounded-xl bg-navy-950 p-3 text-xs text-white shadow-lift"
            style={{ left: `${Math.min(Math.max(((hover.start + hover.end) / 2 / total) * 100, 15), 85)}%` }}>
            <div className="font-semibold" style={{ color: hover.color === '#9ca3af' ? '#d1d5db' : hover.color }}>{hover.label} · {formatTime(hover.start)}</div>
            <div className="mt-1 text-navy-100 line-clamp-3">{hover.text}</div>
          </div>
        )}
        <div className="mt-2 flex justify-between text-[11px] font-mono text-navy-400">
          <span>0:00</span><span>{formatTime(total / 2)}</span><span>{formatTime(total)}</span>
        </div>
      </div>
      {items.length === 0 && <p className="mt-2 text-sm text-navy-400">No claims to plot.</p>}
    </div>
  )
}
