import { AlertTriangle, ArrowLeft, CheckCircle2, CircleHelp, Info, Loader2, ScanFace } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { featureApi } from '../api/endpoints.js'
import { Button, ErrorBanner, Spinner } from '../components/ui/index.jsx'
import { formatTime } from '../utils/format.js'

// Deliberately NOT the verdict colours: authenticity is a separate question from truth.
const OUTCOME = {
  possible_manipulation: { icon: AlertTriangle, cls: 'bg-orange-50 border-orange-200 text-orange-900' },
  no_obvious_indicators: { icon: CheckCircle2, cls: 'bg-navy-50 border-navy-200 text-navy-900' },
  inconclusive: { icon: CircleHelp, cls: 'bg-gray-50 border-gray-200 text-gray-800' },
}
const SEVERITY = { medium: 'bg-orange-100 text-orange-800', low: 'bg-navy-100 text-navy-700', info: 'bg-gray-100 text-gray-600' }
const CHECK_NAMES = { audio: 'Audio splices & silence', timing: 'Frame timing', scene: 'Scene cuts', face: 'Face consistency', av_sync: 'Lip-sync (audio-video)' }

export default function AuthenticityPage() {
  const { videoId } = useParams()
  const [doc, setDoc] = useState(null)
  const [error, setError] = useState(null)
  const [starting, setStarting] = useState(false)
  const timer = useRef(null)

  const load = async () => {
    try {
      const d = await featureApi.authenticity(videoId)
      setDoc(d)
      if (['queued', 'running'].includes(d.status)) timer.current = setTimeout(load, 2500)
    } catch (e) { setError(e) }
  }
  useEffect(() => { load(); return () => clearTimeout(timer.current) }, [videoId]) // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setStarting(true); setError(null)
    try { await featureApi.startAuthenticity(videoId); await load() } catch (e) { setError(e) } finally { setStarting(false) }
  }

  if (!doc && !error) return <Spinner label="Loading…" />
  const r = doc?.result
  const running = ['queued', 'running'].includes(doc?.status)
  const O = r ? OUTCOME[r.outcome] : null

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link to={`/analysis/${videoId}`} className="inline-flex items-center gap-1 text-sm text-navy-500 hover:text-navy-900"><ArrowLeft className="h-4 w-4" />Back to analysis</Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold"><ScanFace className="h-6 w-6" />Media authenticity</h1>
          <p className="text-sm text-navy-500">Signs of editing or manipulation in the video and audio. Separate from fact verification.</p>
        </div>
        <Button onClick={start} loading={starting || running} disabled={running}>{r ? 'Run again' : 'Analyse this video'}</Button>
      </div>
      <ErrorBanner error={error} />
      {doc?.status === 'failed' && <ErrorBanner error={new Error(doc.error || 'Analysis failed')} />}
      {running && <div className="card flex items-center gap-3 p-5 text-sm text-navy-600"><Loader2 className="h-5 w-5 animate-spin" />Analysing frames, audio and lip-sync… this takes up to a minute.</div>}
      {doc?.status === 'not_started' && !running && (
        <div className="card p-5 text-sm text-navy-600">Not analysed yet. The checks look for splices, frame-timing gaps, lip-sync problems and face inconsistencies.</div>
      )}

      {r && (
        <>
          <div className={`rounded-2xl border p-5 ${O.cls}`}>
            <div className="flex items-center gap-2 text-lg font-bold"><O.icon className="h-5 w-5" />{r.label}</div>
            <p className="mt-1 text-sm">{r.summary}</p>
            <p className="mt-2 text-xs opacity-80">{r.detector?.note} Analysed the first {formatTime(r.analysed_seconds)}.</p>
          </div>

          <div className="grid md:grid-cols-5 gap-6">
            <section className="card p-5 md:col-span-2">
              <h2 className="font-bold">Checks</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {Object.entries(r.checks).map(([k, v]) => (
                  <li key={k} className="flex justify-between gap-3">
                    <span className="text-navy-600">{CHECK_NAMES[k] || k}</span>
                    <span className={v === 'assessed' ? 'font-semibold text-navy-900' : 'text-right text-navy-400'}>{v}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 text-xs text-navy-500">
                {r.media.width ? `${r.media.width}×${r.media.height}` : 'Audio only'}{r.media.fps ? ` · ${r.media.fps.toFixed(0)} fps` : ''}
                {r.media.video_codec ? ` · ${r.media.video_codec}` : ''}{r.media.audio_codec ? ` / ${r.media.audio_codec}` : ''}
              </div>
            </section>
            <section className="card p-5 md:col-span-3">
              <h2 className="font-bold">Indicators</h2>
              {r.indicators.length === 0 ? <p className="mt-3 text-sm text-navy-500">No indicators found by the checks that ran.</p> : (
                <ul className="mt-3 space-y-3">
                  {r.indicators.map((i, n) => (
                    <li key={n} className="rounded-xl border border-navy-100 p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${SEVERITY[i.severity]}`}>{i.severity}</span>
                        <span className="font-semibold">{i.name}</span>
                        <span className="ml-auto text-xs text-navy-400">reliability: {i.reliability}</span>
                      </div>
                      <p className="mt-1 text-navy-600">{i.detail}</p>
                      {i.times.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {i.times.map((t) => (
                            <Link key={t} to={`/analysis/${videoId}`} className="rounded-full bg-paper px-2 py-0.5 font-mono text-xs ring-1 ring-navy-100 hover:ring-navy-300">{formatTime(t)}</Link>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section className="card p-5">
            <h2 className="flex items-center gap-2 font-bold"><Info className="h-4 w-4" />Limitations</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-navy-600">{r.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
          </section>
        </>
      )}
    </div>
  )
}
