import { ChevronDown, ExternalLink, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { STANCES, TRUST_STYLES } from '../../utils/format.js'

function credibilityLabel(c) {
  if (c >= 1) return 'Fact-checker'
  if (c >= 0.9) return 'Official / scientific'
  if (c >= 0.8) return 'Established news'
  if (c >= 0.7) return 'Reference'
  return 'General web'
}

const SIGNAL_NAMES = {
  publisher: 'Publisher', primary_source: 'Primary source', author: 'Author', date: 'Date',
  references: 'References', transparency: 'Transparency', corroboration: 'Corroboration',
}

/** Source Trust Analyser result: level badge + the reason behind every signal. */
export function TrustBadge({ trust, fallback }) {
  const [open, setOpen] = useState(false)
  if (!trust) {
    return <span className="inline-flex items-center gap-1 text-navy-500"><ShieldCheck className="h-3.5 w-3.5" />{fallback}</span>
  }
  return (
    <span className="relative inline-block">
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold ring-1 ${TRUST_STYLES[trust.level]}`}>
        <ShieldCheck className="h-3.5 w-3.5" />Trust: {trust.level} ({Math.round(trust.score * 100)})
        <ChevronDown className={`h-3 w-3 transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute z-20 mt-2 w-80 rounded-xl border border-navy-100 bg-white p-3 text-xs shadow-lift">
          <div className="font-semibold text-navy-800">Why this trust level</div>
          <ul className="mt-2 space-y-1.5">
            {trust.signals.map((sg) => (
              <li key={sg.signal} className="flex gap-2">
                <span className="mt-1 h-1.5 w-8 shrink-0 rounded-full bg-navy-100 overflow-hidden">
                  <span className="block h-full bg-navy-700" style={{ width: `${sg.score * 100}%` }} />
                </span>
                <span><b>{SIGNAL_NAMES[sg.signal] || sg.signal}:</b> {sg.value}. <span className="text-navy-500">{sg.reason}</span></span>
              </li>
            ))}
          </ul>
          {!trust.metadata_checked && <p className="mt-2 text-navy-400">Page metadata wasn't checked, so author and references are scored neutrally.</p>}
          <p className="mt-2 text-navy-400">Domain reputation is one signal, never the whole score.</p>
        </div>
      )}
    </span>
  )
}

export default function EvidencePanel({ evidence, highlight }) {
  if (!evidence?.length) {
    return <p className="text-sm text-navy-400">No sources were retrieved for this claim.</p>
  }
  const relevant = evidence.filter((e) => e.stance !== 'irrelevant')
  const others = evidence.filter((e) => e.stance === 'irrelevant')

  const row = (e) => {
    const n = evidence.indexOf(e) + 1
    const st = STANCES[e.stance] || STANCES.irrelevant
    return (
      <li key={e.id} id={`ev-${e.id}`}
        className={`rounded-xl border p-4 transition ${highlight === n ? 'border-navy-500 bg-navy-50/60' : 'border-navy-100 bg-white'}`}>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-md bg-navy-900 px-1.5 py-0.5 font-mono font-bold text-white">E{n}</span>
          <span className={`rounded-full px-2 py-0.5 font-semibold ${st.cls}`}>{st.label}</span>
          <TrustBadge trust={e.trust} fallback={credibilityLabel(e.credibility)} />
          {e.published && <span className="text-navy-400">· {e.published.slice(0, 10)}</span>}
        </div>
        <a href={e.url} target="_blank" rel="noopener noreferrer" className="mt-2 flex items-start gap-1.5 font-semibold text-sm text-navy-900 hover:underline">
          <span className="line-clamp-2">{e.title}</span><ExternalLink className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        </a>
        <div className="text-xs text-navy-400">{e.source_name} · {new URL(e.url).hostname.replace(/^www\./, '')}</div>
        {e.quote ? (
          <blockquote className="mt-2 border-l-2 border-navy-300 pl-3 text-sm text-navy-700">“{e.quote}”</blockquote>
        ) : (
          <p className="mt-2 text-sm text-navy-600 line-clamp-3">{e.snippet}</p>
        )}
      </li>
    )
  }

  return (
    <div className="space-y-3">
      {relevant.length > 0 && <ul className="space-y-3">{relevant.map(row)}</ul>}
      {others.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs font-semibold text-navy-500 hover:text-navy-800">
            {others.length} other retrieved source{others.length > 1 ? 's' : ''} (not directly relevant)
          </summary>
          <ul className="mt-3 space-y-3">{others.map(row)}</ul>
        </details>
      )}
    </div>
  )
}
