import { Activity } from 'lucide-react'

const STAGES = [['capture', 'Capture'], ['transcribe', 'Transcribe'], ['extract_claims', 'Find claims'], ['verify', 'Verify']]
const KIND = { analysis: 'Analysis', retry: 'Retry', recheck: 'Evidence re-check', scheduled: 'Scheduled re-check' }

const secs = (s) => (s == null ? '—' : s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${s.toFixed(1)}s`)

/** Measured timings and API usage for the latest run: real numbers for the "how fast / how much" question. */
export default function RunStatsPanel({ metrics }) {
  if (!metrics) return null
  const stages = STAGES.filter(([k]) => metrics.stage_seconds?.[k] != null)
  const max = Math.max(...stages.map(([k]) => metrics.stage_seconds[k]), 0.01)
  const tiles = [
    ['Claims verified', metrics.claims_verified],
    ['LLM calls', metrics.llm_calls],
    ['Search queries', metrics.search_queries],
    ['Cache hits', metrics.cache_hit_rate == null ? '—' : `${Math.round(metrics.cache_hit_rate * 100)}%`],
  ]
  return (
    <section className="card p-5" aria-label="Run statistics">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-bold"><Activity className="h-5 w-5 text-navy-600" />Run stats</h2>
        <span className="text-xs text-navy-500">{KIND[metrics.kind] || metrics.kind} · {secs(metrics.total_seconds)}</span>
      </div>
      {stages.length > 0 && (
        <dl className="mt-3 space-y-1.5">
          {stages.map(([k, label]) => (
            <div key={k} className="flex items-center gap-3 text-xs">
              <dt className="w-20 text-navy-500">{label}</dt>
              <dd className="flex-1 h-1.5 rounded-full bg-navy-100 overflow-hidden">
                <div className="h-full bg-navy-700" style={{ width: `${(metrics.stage_seconds[k] / max) * 100}%` }} />
              </dd>
              <span className="w-14 text-right tabular-nums font-semibold">{secs(metrics.stage_seconds[k])}</span>
            </div>
          ))}
        </dl>
      )}
      <div className="mt-4 grid grid-cols-4 gap-2">
        {tiles.map(([label, v]) => (
          <div key={label} className="rounded-lg bg-paper border border-navy-100 p-2 text-center">
            <div className="font-display text-lg font-extrabold tabular-nums">{v ?? 0}</div>
            <div className="text-[11px] text-navy-500 leading-tight">{label}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-navy-500">
        {metrics.audio_minutes ? `${metrics.audio_minutes} min of audio · ` : ''}
        {(metrics.llm_input_tokens + metrics.llm_output_tokens).toLocaleString()} LLM tokens
        {metrics.estimated_cost_usd != null ? ` · est. cost $${metrics.estimated_cost_usd.toFixed(3)}` : ' · set PRICE_* in .env for a cost estimate'}
      </p>
    </section>
  )
}
