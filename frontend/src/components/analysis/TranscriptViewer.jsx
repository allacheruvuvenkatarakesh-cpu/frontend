import { Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { formatTime, verdictMeta } from '../../utils/format.js'

export default function TranscriptViewer({ transcript, claims, currentTime, onSeek, onSelectClaim }) {
  const [q, setQ] = useState('')
  const activeRef = useRef(null)
  const boxRef = useRef(null)

  // which claim (if any) each segment belongs to
  const claimBySegment = useMemo(() => {
    const map = new Map()
    for (const c of claims) {
      for (const s of transcript.segments) {
        if (s.start < c.end && s.end > c.start && !map.has(s.id)) map.set(s.id, c)
      }
    }
    return map
  }, [claims, transcript])

  const activeId = useMemo(() => {
    if (currentTime == null) return null
    return transcript.segments.find((s) => currentTime >= s.start && currentTime < s.end)?.id ?? null
  }, [currentTime, transcript])

  useEffect(() => {
    const box = boxRef.current, el = activeRef.current
    if (box && el) box.scrollTo({ top: el.offsetTop - box.clientHeight / 3, behavior: 'smooth' })
  }, [activeId])

  const term = q.trim().toLowerCase()
  const segments = term ? transcript.segments.filter((s) => s.text.toLowerCase().includes(term)) : transcript.segments

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-bold">Transcript</h2>
        {transcript.language && <span className="text-xs uppercase text-navy-400">{transcript.language}</span>}
      </div>
      <div className="relative mt-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-navy-300" />
        <input className="input pl-9 py-2" placeholder="Search transcript" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search transcript" />
      </div>
      <div ref={boxRef} className="relative mt-3 max-h-96 overflow-y-auto scroll-thin pr-1 space-y-1">
        {segments.map((s) => {
          const c = claimBySegment.get(s.id)
          const m = c?.verification ? verdictMeta(c.verification.verdict) : null
          const active = s.id === activeId
          return (
            <button key={s.id} ref={active ? activeRef : null}
              onClick={() => { onSeek(s.start); if (c) onSelectClaim(c) }}
              className={`group flex w-full gap-3 rounded-lg px-2 py-1.5 text-left text-sm transition
                ${active ? 'bg-navy-100' : 'hover:bg-navy-50'}`}
              style={m ? { boxShadow: `inset 3px 0 0 ${m.color}` } : undefined}>
              <span className="w-12 shrink-0 pt-0.5 font-mono text-xs text-navy-400 group-hover:text-navy-700">{formatTime(s.start)}</span>
              <span className={m ? 'text-navy-900' : 'text-navy-600'}>{s.text}</span>
            </button>
          )
        })}
        {segments.length === 0 && <p className="py-6 text-center text-sm text-navy-400">No matches.</p>}
      </div>
    </div>
  )
}
