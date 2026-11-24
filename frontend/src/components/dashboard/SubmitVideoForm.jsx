import { AnimatePresence, motion } from 'framer-motion'
import { FileVideo, Link2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { videoApi } from '../../api/endpoints.js'
import { Button, ErrorBanner } from '../ui/index.jsx'

const ACCEPT = '.mp4,.webm,.mov,.mkv,.m4v,.avi,.3gp,.mp3,.m4a,.wav,.ogg,.aac,.flac,video/*,audio/*'
const MAX_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB || 500)

export default function SubmitVideoForm() {
  const [mode, setMode] = useState('url')
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState(null)
  const [progress, setProgress] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [drag, setDrag] = useState(false)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const pickFile = (f) => {
    setError(null)
    if (!f) return
    if (f.size > MAX_MB * 1024 * 1024) { setError(new Error(`File is larger than ${MAX_MB} MB`)); return }
    setFile(f)
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const video = mode === 'url'
        ? await videoApi.submitUrl(url.trim(), title.trim())
        : await videoApi.upload(file, title.trim(), setProgress)
      navigate(`/analysis/${video.id}`)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
      setProgress(null)
    }
  }

  const tab = (key, Icon, label) => (
    <button type="button" role="tab" aria-selected={mode === key} onClick={() => { setMode(key); setError(null) }}
      className={`relative flex-1 flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-semibold transition
        ${mode === key ? 'text-white' : 'text-navy-600 hover:text-navy-900'}`}>
      {mode === key && <motion.span layoutId="tab" className="absolute inset-0 rounded-lg bg-navy-900" />}
      <span className="relative flex items-center gap-2"><Icon className="h-4 w-4" />{label}</span>
    </button>
  )

  return (
    <form onSubmit={submit} className="card p-6">
      <h2 className="text-lg font-bold">Analyse a video</h2>
      <p className="text-sm text-navy-500">Public videos only. Analysis takes about 1–3 minutes for a 10-minute video.</p>

      <div role="tablist" className="mt-5 flex gap-1 rounded-xl bg-navy-50 p-1">
        {tab('url', Link2, 'Video link')}
        {tab('upload', Upload, 'Upload file')}
      </div>

      <div className="mt-5 space-y-4">
        <AnimatePresence mode="wait">
          {mode === 'url' ? (
            <motion.div key="url" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 8 }}>
              <label className="label" htmlFor="video-url">Video URL</label>
              <input id="video-url" type="url" required className="input" placeholder="https://www.youtube.com/watch?v=…"
                value={url} onChange={(e) => setUrl(e.target.value)} />
              <p className="mt-1.5 text-xs text-navy-400">YouTube, Vimeo, Dailymotion, X, TikTok, Facebook, Instagram, or a direct .mp4/.mp3 link.</p>
            </motion.div>
          ) : (
            <motion.div key="upload" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}>
              <div
                onClick={() => inputRef.current?.click()}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); pickFile(e.dataTransfer.files?.[0]) }}
                role="button" tabIndex={0}
                className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center cursor-pointer transition
                  ${drag ? 'border-navy-500 bg-navy-50' : 'border-navy-200 hover:border-navy-400'}`}>
                <FileVideo className="h-8 w-8 text-navy-400" />
                {file ? (
                  <p className="mt-3 text-sm font-semibold">{file.name} <span className="text-navy-400 font-normal">({(file.size / 1048576).toFixed(1)} MB)</span></p>
                ) : (
                  <p className="mt-3 text-sm"><span className="font-semibold">Click to choose</span> or drag a video here</p>
                )}
                <p className="mt-1 text-xs text-navy-400">MP4, WebM, MOV, MKV or audio files · up to {MAX_MB} MB</p>
              </div>
              <input ref={inputRef} type="file" accept={ACCEPT} hidden data-testid="file-input" onChange={(e) => pickFile(e.target.files?.[0])} />
            </motion.div>
          )}
        </AnimatePresence>

        <div>
          <label className="label" htmlFor="video-title">Title <span className="text-navy-400 font-normal">(optional)</span></label>
          <input id="video-title" className="input" maxLength={200} placeholder="e.g. Budget speech clip" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>

        <ErrorBanner error={error} />

        {progress != null && (
          <div className="h-2 rounded-full bg-navy-100 overflow-hidden" aria-label="Upload progress">
            <div className="h-full bg-navy-700 transition-all" style={{ width: `${progress}%` }} />
          </div>
        )}

        <Button type="submit" loading={busy} disabled={mode === 'upload' ? !file : !url} className="w-full py-3">
          {busy ? (progress != null ? `Uploading ${progress}%` : 'Submitting…') : 'Start analysis'}
        </Button>
      </div>
    </form>
  )
}
