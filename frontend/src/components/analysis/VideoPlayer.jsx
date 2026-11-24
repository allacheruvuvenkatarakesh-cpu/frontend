import { ExternalLink, FileAudio } from 'lucide-react'
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { apiBase } from '../../api/client.js'
import { videoApi } from '../../api/endpoints.js'
import { formatTime } from '../../utils/format.js'

/**
 * Plays the video from the best available source and exposes seekTo(seconds):
 *  - uploaded / direct files: streamed from the backend with a short-lived media token
 *  - YouTube / Vimeo: privacy-friendly embeds controlled via postMessage
 *  - other platforms: link out to the original at the right timestamp
 */
const VideoPlayer = forwardRef(function VideoPlayer({ video, onTime }, ref) {
  const videoEl = useRef(null)
  const iframeEl = useRef(null)
  const [src, setSrc] = useState(null)
  const [err, setErr] = useState(null)
  const isAudio = /\.(mp3|m4a|wav|ogg|aac|flac)$/i.test(video.source_url || '') || false

  useEffect(() => {
    if (!video.playable) return
    let cancelled = false
    videoApi.mediaToken(video.id)
      .then((t) => !cancelled && setSrc(`${apiBase}${t.stream_url}`))
      .catch((e) => !cancelled && setErr(e))
    return () => { cancelled = true }
  }, [video.id, video.playable])

  useImperativeHandle(ref, () => ({
    seekTo(seconds) {
      const s = Math.max(0, seconds - 1) // start a second early for context
      if (videoEl.current) {
        videoEl.current.currentTime = s
        videoEl.current.play().catch(() => {})
      } else if (iframeEl.current && video.platform === 'youtube') {
        const w = iframeEl.current.contentWindow
        w?.postMessage(JSON.stringify({ event: 'command', func: 'seekTo', args: [s, true] }), '*')
        w?.postMessage(JSON.stringify({ event: 'command', func: 'playVideo', args: [] }), '*')
      } else if (iframeEl.current && video.platform === 'vimeo') {
        const w = iframeEl.current.contentWindow
        w?.postMessage({ method: 'setCurrentTime', value: s }, '*')
        w?.postMessage({ method: 'play' }, '*')
      } else if (video.source_url) {
        window.open(externalAt(video, s), '_blank', 'noopener')
      }
      onTime?.(seconds)
    },
  }), [video, onTime])

  if (video.playable) {
    if (err) return <Placeholder video={video} note="This file could not be loaded for playback." />
    if (!src) return <div className="aspect-video rounded-2xl bg-navy-950/90 animate-pulse" />
    return (
      <video ref={videoEl} src={src} controls preload="metadata" className={`w-full rounded-2xl bg-black ${isAudio ? 'h-16' : 'aspect-video'}`}
        onTimeUpdate={(e) => onTime?.(e.currentTarget.currentTime)} />
    )
  }
  if (video.embed_url) {
    return (
      <iframe ref={iframeEl} src={video.embed_url} title={video.title} className="w-full aspect-video rounded-2xl bg-black"
        allow="accelerometer; autoplay; encrypted-media; picture-in-picture" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />
    )
  }
  return <Placeholder video={video} />
})

function externalAt(video, s) {
  const url = new URL(video.source_url)
  if (video.platform === 'youtube') url.searchParams.set('t', `${Math.floor(s)}s`)
  return url.toString()
}

function Placeholder({ video, note }) {
  return (
    <div className="aspect-video rounded-2xl bg-navy-950 text-navy-100 flex flex-col items-center justify-center text-center p-6">
      <FileAudio className="h-8 w-8 text-navy-400" />
      <p className="mt-3 text-sm">{note || 'In-app preview is not available for this source.'}</p>
      {video.source_url && (
        <a href={video.source_url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-white underline">
          Open original <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
      {video.duration ? <p className="mt-2 text-xs text-navy-400">Duration {formatTime(video.duration)}</p> : null}
    </div>
  )
}

export default VideoPlayer
