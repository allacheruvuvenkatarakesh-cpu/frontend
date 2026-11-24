import { AlertTriangle, ArrowLeft, Download, ExternalLink, Filter, Fingerprint, Languages, Network, ScanFace } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { downloadFile } from '../api/client.js'
import { analysisApi, featureApi, fingerprintApi } from '../api/endpoints.js'
import { useAuth } from '../context/AuthContext.jsx'
import ClaimCard from '../components/analysis/ClaimCard.jsx'
import ProgressTracker from '../components/analysis/ProgressTracker.jsx'
import RunStatsPanel from '../components/analysis/RunStatsPanel.jsx'
import SummaryPanel from '../components/analysis/SummaryPanel.jsx'
import TranscriptViewer from '../components/analysis/TranscriptViewer.jsx'
import TruthTimeline from '../components/analysis/TruthTimeline.jsx'
import VideoPlayer from '../components/analysis/VideoPlayer.jsx'
import TruthFingerprintCard from '../components/fingerprint/TruthFingerprintCard.jsx'
import { Button, EmptyState, ErrorBanner, Spinner } from '../components/ui/index.jsx'
import { useAnalysis } from '../hooks/useAnalysis.js'
import { formatDate, formatTime, isActive, LANGUAGES, VERDICTS } from '../utils/format.js'

export default function AnalysisPage() {
  const { videoId } = useParams()
  const { data, error, loading, retry, recheck } = useAnalysis(videoId)
  const [selectedId, setSelectedId] = useState(null)
  const [time, setTime] = useState(null)
  const [filter, setFilter] = useState('all')
  const [fingerprint, setFingerprint] = useState(null)
  const { user } = useAuth()
  const [lang, setLang] = useState(user?.preferred_language || 'en')
  const [translation, setTranslation] = useState(null)
  const [translating, setTranslating] = useState(false)
  const [reportBusy, setReportBusy] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [params] = useSearchParams()
  const player = useRef(null)
  const cardRefs = useRef({})
  const runStatus = data?.status?.status

  const seek = useCallback((s) => player.current?.seekTo(s), [])
  const selectClaim = useCallback((c) => {
    const id = c.claim_id || c.id
    setSelectedId(id)
    setTimeout(() => cardRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 60)
  }, [])

  const claims = useMemo(() => data?.claims || [], [data])

  // Truth Fingerprint becomes available once the analysis completes
  useEffect(() => {
    if (runStatus !== 'completed') return
    let cancelled = false
    fingerprintApi.get(videoId).then((f) => !cancelled && setFingerprint(f)).catch(() => {})
    return () => { cancelled = true }
  }, [videoId, runStatus])

  // results in the selected language (machine translation, numbers checked server-side)
  useEffect(() => {
    if (runStatus !== 'completed' || lang === 'en') { setTranslation(null); return }
    let cancelled = false
    setTranslating(true)
    analysisApi.translation(videoId, lang)
      .then((t) => !cancelled && setTranslation(t))
      .catch((e) => !cancelled && setActionError(e))
      .finally(() => !cancelled && setTranslating(false))
    return () => { cancelled = true }
  }, [videoId, lang, runStatus])

  const downloadReport = async () => {
    setReportBusy(true)
    setActionError(null)
    try {
      const r = await featureApi.generateReport(videoId)
      await downloadFile(`/reports/${r.report_id}`, `livetruth-report-${r.fingerprint_id || r.report_id}.pdf`)
    } catch (e) {
      setActionError(e)
    } finally {
      setReportBusy(false)
    }
  }

  // deep link from the comparison page: /analysis/:id?claim=<claimId>
  const deepClaim = params.get('claim')
  useEffect(() => {
    const c = deepClaim && claims.find((x) => x.id === deepClaim)
    if (c) selectClaim(c)
  }, [deepClaim, claims, selectClaim])
  const shown = filter === 'all' ? claims : claims.filter((c) => (c.verification?.verdict || 'unverified') === filter)
  const timeline = useMemo(() => {
    if (data?.timeline?.length) return data.timeline
    // while verifying, plot claims verified so far
    return claims.filter((c) => c.verification).map((c) => ({
      claim_id: c.id, start: c.start, end: Math.max(c.end, c.start + 1), verdict: c.verification.verdict,
      color: c.verification.color, label: c.verification.label, text: c.text,
    }))
  }, [data, claims])

  if (loading && !data) return <Spinner label="Loading analysis…" />
  if (error && !data) {
    return <EmptyState title="Couldn't load this analysis" action={<Button as={Link} to="/history">Back to history</Button>}>{error.message}</EmptyState>
  }
  if (!data) return null

  const { video, status, transcript, summary } = data
  const duration = video.duration || transcript?.segments?.at(-1)?.end
  const running = isActive(status.status)

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-2">
        <Link to="/history" className="inline-flex items-center gap-1 text-sm text-navy-500 hover:text-navy-900"><ArrowLeft className="h-4 w-4" />All analyses</Link>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-extrabold truncate">{video.title}</h1>
            <p className="text-sm text-navy-500">
              {video.platform ? video.platform[0].toUpperCase() + video.platform.slice(1) : video.source_type === 'upload' ? 'Uploaded file' : 'Direct link'}
              {duration ? ` · ${formatTime(duration)}` : ''} · {formatDate(video.created_at)}
            </p>
          </div>
          {video.source_url && (
            <a href={video.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-sm font-semibold text-navy-600 hover:text-navy-900">
              Original source <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>

      {status.status === 'completed' && (
        <div className="card flex flex-wrap items-center gap-2 p-3">
          <label className="inline-flex items-center gap-2 rounded-xl border border-navy-200 px-3 py-1.5 text-sm">
            <Languages className="h-4 w-4 text-navy-500" />
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="bg-transparent outline-none" aria-label="Results language">
              {Object.entries(LANGUAGES).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
            {translating && <span className="text-xs text-navy-400">translating…</span>}
          </label>
          <Button variant="secondary" onClick={downloadReport} loading={reportBusy}><Download className="h-4 w-4" />PDF report</Button>
          <Button as={Link} variant="secondary" to={`/analysis/${videoId}/graph`}><Network className="h-4 w-4" />Evidence graph</Button>
          <Button as={Link} variant="secondary" to={`/analysis/${videoId}/authenticity`}><ScanFace className="h-4 w-4" />Media authenticity</Button>
          <Button as={Link} variant="secondary" to={`/analysis/${videoId}/fingerprint`}><Fingerprint className="h-4 w-4" />Fingerprint</Button>
          {translation && <span className="ml-auto text-xs text-navy-400">{translation.note}</span>}
        </div>
      )}

      <ErrorBanner error={error || actionError} />
      {data.context_summary?.contradictions?.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm" role="note">
          <div className="flex items-center gap-2 font-semibold text-red-800"><AlertTriangle className="h-4 w-4" />The speaker contradicts themselves</div>
          <ul className="mt-2 space-y-1 text-red-900">
            {data.context_summary.contradictions.map((x) => (
              <li key={x.a + x.b}>
                <button className="font-mono underline" onClick={() => { selectClaim({ id: x.claim_a_id }); seek(x.start_a) }}>{x.a} {formatTime(x.start_a)}</button>
                {' vs '}
                <button className="font-mono underline" onClick={() => { selectClaim({ id: x.claim_b_id }); seek(x.start_b) }}>{x.b} {formatTime(x.start_b)}</button>
                {x.explanation ? `: ${x.explanation}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
      {(running || status.status === 'failed') && <ProgressTracker status={status} onRetry={status.status === 'failed' ? retry : null} />}

      <div className="grid xl:grid-cols-5 gap-6">
        <div className="xl:col-span-3 space-y-6">
          <VideoPlayer ref={player} video={video} onTime={setTime} />
          {(timeline.length > 0 || status.status === 'completed') && (
            <TruthTimeline items={timeline} duration={duration} selectedId={selectedId} currentTime={time}
              onSelect={(it) => { selectClaim(it); seek(it.start) }} />
          )}
          {transcript && <TranscriptViewer transcript={transcript} claims={claims} currentTime={time} onSeek={seek} onSelectClaim={selectClaim} />}
        </div>

        <div className="xl:col-span-2 space-y-6">
          {status.status === 'completed' && <SummaryPanel summary={summary} />}
          {translation?.summary?.translated && (
            <p className="-mt-3 rounded-xl bg-navy-50 px-4 py-3 text-sm text-navy-700" lang={lang}>{translation.summary.text}</p>
          )}
          {fingerprint && (
            <TruthFingerprintCard fingerprint={fingerprint} onRecheck={recheck}
              onSeek={(t) => { selectClaim({ id: t.claim_id }); seek(t.start) }} />
          )}
          {status.status === 'completed' && status.error && (
            <p className="rounded-xl border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800" role="status">{status.error}</p>
          )}
          {status.status === 'completed' && <RunStatsPanel metrics={data.metrics} />}
          {claims.length > 0 && (
            <section aria-label="Claims">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h2 className="font-bold">Claims <span className="text-navy-400 font-medium">({claims.length})</span></h2>
                <label className="flex items-center gap-2 text-sm text-navy-500">
                  <Filter className="h-4 w-4" />
                  <select className="rounded-lg border border-navy-200 bg-white px-2 py-1 text-sm" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter claims by verdict">
                    <option value="all">All verdicts</option>
                    {Object.entries(VERDICTS).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
                  </select>
                </label>
              </div>
              <div className="space-y-4">
                {shown.map((c) => (
                  <ClaimCard key={c.id} ref={(el) => { cardRefs.current[c.id] = el }} claim={c} index={claims.indexOf(c)}
                    selected={selectedId === c.id} onSelect={selectClaim} onSeek={seek}
                    translation={translation?.claims?.[c.id]} lang={translation ? lang : 'en'} />
                ))}
                {shown.length === 0 && <p className="text-sm text-navy-400">No claims with this verdict.</p>}
              </div>
            </section>
          )}
          {status.status === 'completed' && claims.length === 0 && (
            <EmptyState title="No checkable claims found">The speech didn't contain specific factual statements to verify.</EmptyState>
          )}
        </div>
      </div>
      <p className="text-center text-xs text-navy-400">AI verdicts can be wrong. Read the cited evidence before drawing conclusions.</p>
    </div>
  )
}
