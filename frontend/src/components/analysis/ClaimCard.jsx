import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, ChevronDown, Info, Languages, Play } from 'lucide-react'
import { forwardRef, useEffect, useState } from 'react'
import { formatTime, LANGUAGE_NAMES, RISK_STYLES, splitCitations, verdictMeta } from '../../utils/format.js'
import { ConfidenceMeter, VerdictBadge } from '../ui/index.jsx'
import EvidencePanel from './EvidencePanel.jsx'

function ContextFlags({ ctx, onSeek }) {
  if (!ctx || !ctx.flags?.length) return null
  return (
    <div className="mt-3 rounded-xl border border-yellow-200 bg-yellow-50/60 p-3 text-sm">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-yellow-700" />
        <span className="font-semibold text-yellow-900">Context check</span>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${RISK_STYLES[ctx.risk] || RISK_STYLES.unknown}`}>
          {ctx.risk} risk
        </span>
      </div>
      <ul className="mt-2 space-y-2">
        {ctx.flags.map((f) => (
          <li key={f.type}>
            <span className="font-semibold">{f.label}:</span> {f.explanation}
            {f.transcript_quote && (
              <button onClick={() => f.start != null && onSeek?.(f.start)} disabled={f.start == null}
                className="mt-1 block w-full rounded-lg bg-white/70 px-2 py-1 text-left text-xs italic text-navy-600 hover:bg-white">
                {f.start != null && <span className="not-italic font-mono mr-1">{formatTime(f.start)}</span>}“{f.transcript_quote}”
              </button>
            )}
          </li>
        ))}
      </ul>
      {ctx.missing_context && <p className="mt-2 text-xs text-navy-600"><b>Missing context:</b> {ctx.missing_context}</p>}
    </div>
  )
}

const ClaimCard = forwardRef(function ClaimCard({ claim, index, selected, onSelect, onSeek, translation, lang = 'en' }, ref) {
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(null)
  const v = claim.verification
  const meta = verdictMeta(v?.verdict)
  const expanded = open
  useEffect(() => { if (selected) setOpen(true) }, [selected])

  const cite = (n) => {
    setOpen(true)
    setHighlight(n)
    const ev = claim.evidence[n - 1]
    if (ev) setTimeout(() => document.getElementById(`ev-${ev.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50)
  }

  const nonEnglish = claim.language && claim.language !== 'en'
  const tText = translation?.text
  const tExpl = translation?.explanation
  const explanation = tExpl?.translated ? tExpl.text : v?.explanation

  return (
    <motion.article ref={ref} layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className={`card overflow-hidden border-l-4 transition-shadow ${selected ? 'shadow-lift ring-1 ring-navy-300' : ''}`}
      style={{ borderLeftColor: meta.color }} aria-label={`Claim ${claim.code || index + 1}`}>
      <div className="p-5">
        <div className="flex flex-wrap items-center gap-2">
          {claim.code && <span className="font-mono text-xs font-semibold text-navy-400">{claim.code}</span>}
          {v ? <VerdictBadge verdict={v.verdict} lang={lang} /> : <span className="text-xs font-semibold text-navy-400">Checking…</span>}
          <button onClick={() => { onSelect?.(claim); onSeek?.(claim.start) }}
            className="inline-flex items-center gap-1 rounded-full bg-navy-50 px-2.5 py-0.5 text-xs font-mono font-semibold text-navy-700 hover:bg-navy-100"
            aria-label={`Play from ${formatTime(claim.start)}`}>
            <Play className="h-3 w-3" />{formatTime(claim.start)}
          </button>
          <span className="text-xs capitalize text-navy-400">{claim.claim_type}</span>
          {nonEnglish && <span className="inline-flex items-center gap-1 text-xs text-navy-500"><Languages className="h-3.5 w-3.5" />{LANGUAGE_NAMES[claim.language] || claim.language}</span>}
        </div>

        <p className="mt-3 font-semibold leading-snug" lang={claim.language}>{claim.text}</p>
        {nonEnglish && claim.text_en && claim.text_en !== claim.text && (
          <p className="mt-1 text-sm text-navy-600"><span className="text-xs font-semibold uppercase text-navy-400 mr-1">English</span>{claim.text_en}</p>
        )}
        {tText?.translated && tText.text !== claim.text && (
          <p className="mt-1 text-sm text-navy-600" lang={lang}><span className="text-xs font-semibold uppercase text-navy-400 mr-1">{LANGUAGE_NAMES[lang]}</span>{tText.text}</p>
        )}
        {(tText?.warning || tExpl?.warning) && <p className="mt-1 text-xs text-orange-700">{tText?.warning || tExpl?.warning}</p>}
        {claim.original_quote && claim.original_quote !== claim.text && (
          <p className="mt-1.5 text-sm text-navy-500 italic" lang={claim.language}>Said: “{claim.original_quote}”</p>
        )}

        {v && (
          <>
            <p className="mt-3 text-sm text-navy-700 leading-relaxed" lang={tExpl?.translated ? lang : 'en'}>
              {splitCitations(explanation).map((p, i) => p.cite ? (
                <button key={i} onClick={() => cite(p.cite)} className="mx-0.5 rounded bg-navy-100 px-1 font-mono text-[11px] font-bold text-navy-700 hover:bg-navy-200 align-baseline">
                  E{p.cite}
                </button>
              ) : <span key={i}>{p.text}</span>)}
            </p>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <ConfidenceMeter value={v.confidence} color={meta.color} />
              {v.adjusted && (
                <span className="inline-flex items-center gap-1 text-xs text-navy-500" title="The model's suggested verdict was not supported strongly enough by the evidence, so it was downgraded.">
                  <Info className="h-3.5 w-3.5" /> Adjusted by evidence check
                </span>
              )}
            </div>
          </>
        )}

        <ContextFlags ctx={claim.context_analysis} onSeek={onSeek} />

        <button onClick={() => setOpen(!expanded)} aria-expanded={expanded}
          className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-navy-600 hover:text-navy-900">
          {expanded ? 'Hide' : 'Show'} evidence ({claim.evidence.length})
          <ChevronDown className={`h-4 w-4 transition ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="border-t border-navy-100 bg-paper px-5 py-4">
            <EvidencePanel evidence={claim.evidence} highlight={highlight} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  )
})

export default ClaimCard
