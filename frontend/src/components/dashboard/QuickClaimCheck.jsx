import { Search } from 'lucide-react'
import { useState } from 'react'
import { featureApi } from '../../api/endpoints.js'
import { verdictMeta } from '../../utils/format.js'
import EvidencePanel from '../analysis/EvidencePanel.jsx'
import { Button, ConfidenceMeter, ErrorBanner, VerdictBadge } from '../ui/index.jsx'

/** Check one typed claim with the same evidence pipeline (no video, not saved). */
export default function QuickClaimCheck() {
  const [claim, setClaim] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const run = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null); setResult(null)
    try { setResult(await featureApi.checkClaim(claim.trim())) } catch (err) { setError(err) } finally { setBusy(false) }
  }

  const v = result?.verification
  return (
    <section className="card p-6">
      <h2 className="text-lg font-bold">Check a single claim</h2>
      <p className="text-sm text-navy-500">Heard something without a video? Type it and check it against evidence.</p>
      <form onSubmit={run} className="mt-4 flex flex-col sm:flex-row gap-3">
        <input className="input" minLength={10} maxLength={500} required placeholder="e.g. The Great Wall of China is visible from the Moon"
          value={claim} onChange={(e) => setClaim(e.target.value)} aria-label="Claim to check" />
        <Button type="submit" loading={busy} className="shrink-0"><Search className="h-4 w-4" />Check</Button>
      </form>
      <div className="mt-3"><ErrorBanner error={error} /></div>
      {v && (
        <div className="mt-4 rounded-xl border border-navy-100 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <VerdictBadge verdict={v.verdict} size="lg" />
            <ConfidenceMeter value={v.confidence} color={verdictMeta(v.verdict).color} />
          </div>
          <p className="mt-2 text-sm text-navy-700">{v.explanation}</p>
          {result.evidence.length > 0 && <div className="mt-3"><EvidencePanel evidence={result.evidence.map((e, i) => ({ ...e, id: `q${i}` }))} /></div>}
        </div>
      )}
    </section>
  )
}
