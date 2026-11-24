import { motion } from 'framer-motion'
import { AlertTriangle, ArrowRight, GitCompare, Hash, Link2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { analysisApi, fingerprintApi } from '../api/endpoints.js'
import FingerprintGlyph from '../components/fingerprint/FingerprintGlyph.jsx'
import { CountChips } from '../components/fingerprint/TruthFingerprintCard.jsx'
import { EmptyState, ErrorBanner, Spinner, VerdictBadge } from '../components/ui/index.jsx'
import { formatTime, pct, STANCES } from '../utils/format.js'

export const RELATION_STYLES = {
  agree: 'bg-green-50 text-green-700 ring-green-200',
  conflict: 'bg-red-50 text-red-700 ring-red-200',
  partial: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  undetermined: 'bg-gray-100 text-gray-600 ring-gray-200',
}
const EVIDENCE_STYLES = {
  same_evidence: 'text-navy-800', overlapping_evidence: 'text-navy-600',
  independent_evidence: 'text-navy-500', missing_evidence: 'text-navy-400',
}

function Picker({ label, value, onChange, options, exclude }) {
  return (
    <label className="flex-1 min-w-0">
      <span className="label">{label}</span>
      <select className="input" value={value || ''} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose a completed analysis…</option>
        {options.filter((o) => o.video_id !== exclude).map((o) => (
          <option key={o.video_id} value={o.video_id}>
            {o.title}{o.shared_claims != null ? ` — ${o.shared_claims} shared claim${o.shared_claims === 1 ? '' : 's'}` : ''}
          </option>
        ))}
      </select>
    </label>
  )
}

function Side({ side, tag }) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <FingerprintGlyph fingerprint={{ ...side, claims: [] }} size={112} />
      <div className="min-w-0 flex-1">
        <div className="text-xs font-bold text-navy-400">VIDEO {tag}</div>
        <Link to={`/analysis/${side.video.id}`} className="block truncate font-bold hover:underline">{side.video.title}</Link>
        <div className="font-mono text-xs text-navy-500">{side.fingerprint_id}</div>
        <div className="mt-1 text-xs text-navy-500">
          {side.total_claims} claims · evidence {side.evidence_quality.grade} ({Math.round(side.evidence_quality.score)}) · score {side.truth_score == null ? '—' : Math.round(side.truth_score)}
        </div>
        <div className="mt-2"><CountChips counts={side.counts} /></div>
      </div>
    </div>
  )
}

function ClaimSide({ c, videoId, tag }) {
  return (
    <div className="flex-1 min-w-0 rounded-xl bg-paper p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold text-navy-400">VIDEO {tag}</span>
        <VerdictBadge verdict={c.verdict} />
        <Link to={`/analysis/${videoId}?claim=${c.claim_id}`} className="rounded-full bg-white px-2 py-0.5 font-mono text-xs font-semibold text-navy-700 ring-1 ring-navy-100 hover:ring-navy-300"
          aria-label={`Open video ${tag} at ${formatTime(c.start)}`}>▶ {formatTime(c.start)}</Link>
        {c.confidence != null && <span className="text-xs text-navy-500">{pct(c.confidence)} conf.</span>}
      </div>
      <p className="mt-2 text-sm font-medium">{c.text}</p>
    </div>
  )
}

export function MatchCard({ m, a, b }) {
  const ev = m.evidence
  return (
    <motion.article initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="card p-5" aria-label={`${m.relation_label} claim pair`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ${RELATION_STYLES[m.relation]}`}>{m.relation_label}</span>
        <span className={`text-xs font-semibold ${EVIDENCE_STYLES[ev.relation]}`}>{ev.label}</span>
        {m.different_figures && (
          <span className="inline-flex items-center gap-1 rounded-full bg-yellow-50 px-2 py-0.5 text-xs font-semibold text-yellow-800 ring-1 ring-yellow-200">
            <Hash className="h-3 w-3" />Different figures: {m.different_figures.video_a.join(', ')} vs {m.different_figures.video_b.join(', ')}
          </span>
        )}
        <span className="ml-auto text-xs text-navy-400" title={m.match_method === 'semantic' ? 'Matched by meaning (embeddings)' : 'Matched by wording'}>
          {Math.round(m.similarity * 100)}% match · {m.match_method}
        </span>
      </div>
      <div className="mt-3 flex flex-col sm:flex-row gap-3">
        <ClaimSide c={m.claim_a} videoId={a} tag="A" />
        <ClaimSide c={m.claim_b} videoId={b} tag="B" />
      </div>
      <p className="mt-3 text-sm text-navy-700">{m.insight}</p>
      {(ev.shared_sources.length > 0 || ev.only_a.length > 0 || ev.only_b.length > 0) && (
        <div className="mt-3 rounded-xl border border-navy-100 p-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-navy-700">Evidence overlap</span>
            <span className="tabular-nums text-navy-500">{pct(ev.url_overlap)} of sources shared</span>
          </div>
          {ev.shared_sources.length > 0 && (
            <ul className="mt-2 space-y-1">
              {ev.shared_sources.map((s) => {
                const clash = (s.stance_a === 'supports' && s.stance_b === 'refutes') || (s.stance_a === 'refutes' && s.stance_b === 'supports')
                return (
                  <li key={s.url} className={`flex flex-wrap items-center gap-2 rounded-lg px-2 py-1 ${clash ? 'bg-red-50' : 'bg-paper'}`}>
                    {clash && <AlertTriangle className="h-3.5 w-3.5 text-red-600" />}
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline truncate max-w-[14rem]">{s.domain}</a>
                    <span>A: <span className={`rounded px-1 ${STANCES[s.stance_a]?.cls}`}>{STANCES[s.stance_a]?.label}</span></span>
                    <span>B: <span className={`rounded px-1 ${STANCES[s.stance_b]?.cls}`}>{STANCES[s.stance_b]?.label}</span></span>
                  </li>
                )
              })}
            </ul>
          )}
          {(ev.only_a.length > 0 || ev.only_b.length > 0) && (
            <div className="mt-2 grid sm:grid-cols-2 gap-2 text-navy-500">
              <div>Only A: {ev.only_a.join(', ') || '—'}</div>
              <div>Only B: {ev.only_b.join(', ') || '—'}</div>
            </div>
          )}
        </div>
      )}
    </motion.article>
  )
}

export default function ComparePage() {
  const [params, setParams] = useSearchParams()
  const a = params.get('a') || ''
  const b = params.get('b') || ''
  const [completed, setCompleted] = useState([])
  const [candidates, setCandidates] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')

  const set = (key, value) => {
    const next = new URLSearchParams(params)
    value ? next.set(key, value) : next.delete(key)
    if (key === 'a' && value === b) next.delete('b')
    setParams(next, { replace: true })
  }

  useEffect(() => {
    analysisApi.list({ pageSize: 50, status: 'completed' }).then((d) => setCompleted(d.items)).catch(setError)
  }, [])

  useEffect(() => {
    setCandidates(null)
    if (!a) return
    fingerprintApi.candidates(a).then(setCandidates).catch(() => setCandidates([]))
  }, [a])

  useEffect(() => {
    setResult(null)
    if (!a || !b) return
    setLoading(true)
    setError(null)
    fingerprintApi.compare(a, b).then(setResult).catch(setError).finally(() => setLoading(false))
  }, [a, b])

  const bOptions = useMemo(() => candidates || completed, [candidates, completed])
  const matches = result ? result.matches.filter((m) => filter === 'all' || m.relation === filter) : []
  const s = result?.summary

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-extrabold"><GitCompare className="h-6 w-6" />Compare videos</h1>
        <p className="text-sm text-navy-500">Find the claims two videos share, and see whether they rest on the same evidence or present conflicting information.</p>
      </div>

      <div className="card p-5 flex flex-col sm:flex-row items-end gap-4">
        <Picker label="Video A" value={a} onChange={(v) => set('a', v)} options={completed} />
        <ArrowRight className="hidden sm:block h-5 w-5 mb-3 text-navy-300" />
        <Picker label={candidates ? 'Video B (ranked by shared claims)' : 'Video B'} value={b} onChange={(v) => set('b', v)} options={bOptions} exclude={a} />
      </div>

      <ErrorBanner error={error} />
      {completed.length < 2 && !result && (
        <EmptyState icon={Link2} title="You need two completed analyses">Analyse at least two videos, ideally ones that talk about the same topic, then compare them here.</EmptyState>
      )}
      {loading && <Spinner label="Matching claims and evidence…" />}

      {result && (
        <>
          <div className="grid md:grid-cols-2 gap-4">
            <Side side={result.video_a} tag="A" />
            <Side side={result.video_b} tag="B" />
          </div>

          <div className={`card p-5 ${s.has_conflicts ? 'border-red-200' : ''}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-bold">{s.headline}</h2>
              {s.avg_evidence_overlap != null && <span className="text-sm text-navy-500">Average evidence overlap {pct(s.avg_evidence_overlap)}</span>}
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {[['all', `All (${s.shared_claims})`], ['conflict', `Conflicting (${s.relation_counts.conflict})`], ['partial', `Partly (${s.relation_counts.partial})`],
                ['agree', `Consistent (${s.relation_counts.agree})`], ['undetermined', `Undetermined (${s.relation_counts.undetermined})`]].map(([k, label]) => (
                <button key={k} onClick={() => setFilter(k)}
                  className={`rounded-full px-3 py-1 font-semibold ring-1 ${filter === k ? 'bg-navy-900 text-white ring-navy-900' : 'bg-white text-navy-600 ring-navy-200 hover:bg-navy-50'}`}>{label}</button>
              ))}
            </div>
            <p className="mt-3 text-xs text-navy-500">
              {s.only_in_a} claim{s.only_in_a === 1 ? '' : 's'} only in A · {s.only_in_b} only in B
              {s.shared_domains.length > 0 && <> · Sources used by both: {s.shared_domains.join(', ')}</>}
            </p>
          </div>

          <div className="space-y-4">
            {matches.map((m) => <MatchCard key={m.claim_a.claim_id + m.claim_b.claim_id} m={m} a={a} b={b} />)}
            {s.shared_claims > 0 && matches.length === 0 && <p className="text-sm text-navy-400">No pairs in this category.</p>}
          </div>
        </>
      )}
    </div>
  )
}
