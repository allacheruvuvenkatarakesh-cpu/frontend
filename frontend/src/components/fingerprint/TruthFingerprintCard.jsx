import { Check, ChevronDown, Copy, Fingerprint, GitCompare, History, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDate, formatTime, pct, VERDICTS } from '../../utils/format.js'
import FingerprintGlyph from './FingerprintGlyph.jsx'

export function CountChips({ counts = {} }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {Object.entries(VERDICTS).map(([k, m]) => (
        <div key={k} className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs ${m.bg} ${m.text}`}>
          <span className="flex items-center gap-1.5 font-medium"><span className="h-2 w-2 rounded-full" style={{ background: m.color }} />{m.label}</span>
          <span className="font-bold tabular-nums">{counts[k] ?? 0}</span>
        </div>
      ))}
    </div>
  )
}

export function EvidenceQuality({ q }) {
  const rows = [
    ['Claims with evidence', q.coverage],
    ['Source credibility', q.avg_credibility],
    ['Source diversity', q.source_diversity],
    ['Evidence confidence', q.avg_confidence],
  ]
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold">Evidence quality</span>
        <span className="text-sm"><span className="font-display font-extrabold text-lg">{q.grade}</span>
          <span className="text-navy-500"> · {q.label} · {Math.round(q.score)}/100</span></span>
      </div>
      <dl className="mt-2 space-y-1.5">
        {rows.map(([label, v]) => (
          <div key={label} className="flex items-center gap-3 text-xs">
            <dt className="w-36 text-navy-500">{label}</dt>
            <dd className="flex-1 h-1.5 rounded-full bg-navy-100 overflow-hidden"><div className="h-full bg-navy-700" style={{ width: pct(v) }} /></dd>
            <span className="w-9 text-right tabular-nums font-semibold">{pct(v)}</span>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-navy-400">
        {q.grounded_sources} grounded sources from {q.distinct_domains} sites{q.fact_checker_sources ? `, ${q.fact_checker_sources} from fact-checkers` : ''}.
      </p>
    </div>
  )
}

function VersionRow({ v, first }) {
  const [open, setOpen] = useState(false)
  const c = v.changes
  const summary = !c ? 'First verification'
    : c.unchanged ? 'Re-verified: no changes'
    : [c.verdict_changes.length && `${c.verdict_changes.length} verdict change${c.verdict_changes.length > 1 ? 's' : ''}`,
       c.added_claims.length && `${c.added_claims.length} new`, c.removed_claims.length && `${c.removed_claims.length} removed`]
      .filter(Boolean).join(' · ')
  const hasDetail = c && !c.unchanged
  return (
    <li className="relative pl-5">
      <span className={`absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full ${first ? 'bg-navy-900' : 'bg-navy-300'}`} />
      <button className="w-full text-left" onClick={() => hasDetail && setOpen(!open)} aria-expanded={open} disabled={!hasDetail}>
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold">v{v.version} · <span className="font-mono text-navy-500">{v.content_hash}</span>
            {v.trigger && <span className="ml-1 font-normal text-navy-400">· {TRIGGERS[v.trigger] || v.trigger}</span>}</span>
          <span className="text-navy-400">{formatDate(v.verified_at)}</span>
        </div>
        <div className="mt-0.5 flex items-center gap-1 text-xs text-navy-600">
          {summary} · score {v.truth_score == null ? '—' : Math.round(v.truth_score)} · evidence {v.evidence_grade}
          {hasDetail && <ChevronDown className={`h-3.5 w-3.5 transition ${open ? 'rotate-180' : ''}`} />}
        </div>
      </button>
      {open && (
        <ul className="mt-2 space-y-1 text-xs">
          {c.verdict_changes.map((x) => (
            <li key={x.text} className="rounded-lg bg-paper px-2 py-1.5">
              <span className="font-mono text-navy-400 mr-1">{formatTime(x.start)}</span>{x.text}
              <span className="ml-1 font-semibold" style={{ color: VERDICTS[x.from]?.color }}>{VERDICTS[x.from]?.label}</span>
              {' → '}<span className="font-semibold" style={{ color: VERDICTS[x.to]?.color }}>{VERDICTS[x.to]?.label}</span>
            </li>
          ))}
          {c.added_claims.map((x) => <li key={x.text} className="rounded-lg bg-paper px-2 py-1.5">+ {x.text}</li>)}
          {c.removed_claims.map((x) => <li key={x.text} className="rounded-lg bg-paper px-2 py-1.5 text-navy-400 line-through">{x.text}</li>)}
        </ul>
      )}
    </li>
  )
}

const TRIGGERS = { analysis: 'First analysis', retry: 'Retry', recheck: 'Evidence re-check', scheduled: 'Scheduled re-check' }

export default function TruthFingerprintCard({ fingerprint, onSeek, onRecheck }) {
  const [copied, setCopied] = useState(false)
  const [rechecking, setRechecking] = useState(false)
  const fp = fingerprint
  const copy = async () => {
    try { await navigator.clipboard.writeText(fp.fingerprint_id); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { /* clipboard blocked */ }
  }
  const versions = [...(fp.versions || [])].reverse()

  return (
    <section className="card p-5" aria-label="Truth Fingerprint">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-bold"><Fingerprint className="h-5 w-5 text-navy-600" />Truth Fingerprint</h2>
        <button onClick={copy} className="inline-flex items-center gap-1.5 rounded-lg bg-navy-50 px-2.5 py-1 font-mono text-xs font-semibold text-navy-800 hover:bg-navy-100"
          aria-label="Copy fingerprint ID">
          {fp.fingerprint_id}{copied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>

      <div className="mt-4 flex items-center gap-5">
        <FingerprintGlyph fingerprint={fp} />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-navy-400">Claims extracted</div>
          <div className="font-display text-3xl font-extrabold tabular-nums">{fp.total_claims}</div>
          <div className="mt-2"><CountChips counts={fp.counts} /></div>
        </div>
      </div>

      <div className="mt-5"><EvidenceQuality q={fp.evidence_quality} /></div>

      {fp.timestamps.length > 0 && (
        <div className="mt-5">
          <div className="text-sm font-semibold">Original video timestamps</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {fp.timestamps.map((t) => (
              <button key={t.claim_id} onClick={() => onSeek?.(t)}
                className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 font-mono text-xs ring-1 ring-navy-100 hover:ring-navy-300"
                aria-label={`Jump to ${formatTime(t.start)} (${VERDICTS[t.verdict]?.label})`}>
                <span className="h-2 w-2 rounded-full" style={{ background: VERDICTS[t.verdict]?.color }} />{formatTime(t.start)}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5">
        <div className="flex items-center gap-1.5 text-sm font-semibold"><History className="h-4 w-4" />Verification history</div>
        <ol className="mt-2 space-y-3 border-l border-navy-100 ml-1 pl-1">
          {versions.map((v, i) => <VersionRow key={v.version} v={v} first={i === 0} />)}
        </ol>
      </div>

      {onRecheck && (
        <button disabled={rechecking}
          onClick={async () => { setRechecking(true); try { await onRecheck() } finally { setRechecking(false) } }}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy-800 disabled:opacity-50"
          title="Search for fresh evidence for the same claims. Adds a new fingerprint version if anything changes.">
          <RefreshCw className={`h-4 w-4 ${rechecking ? 'animate-spin' : ''}`} /> Re-check evidence
        </button>
      )}

      <Link to={`/compare?a=${fp.video.id}`}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-navy-200 px-4 py-2.5 text-sm font-semibold text-navy-900 hover:bg-navy-50">
        <GitCompare className="h-4 w-4" /> Compare with another video
      </Link>
    </section>
  )
}
