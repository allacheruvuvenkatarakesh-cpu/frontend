import { useCallback, useEffect, useRef, useState } from 'react'
import { analysisApi } from '../api/endpoints.js'
import { isActive } from '../utils/format.js'

const POLL_MS = 2500

/** Loads an analysis and polls its status until it finishes, then loads full results. */
export function useAnalysis(videoId) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [run, setRun] = useState(0)
  const timer = useRef(null)

  const load = useCallback(async (signal) => {
    try {
      const d = await analysisApi.get(videoId, signal)
      setData(d)
      setError(null)
      return d
    } catch (e) {
      if (e.name !== 'AbortError') setError(e)
      return null
    } finally {
      setLoading(false)
    }
  }, [videoId])

  useEffect(() => {
    const ctrl = new AbortController()
    let lastProgress = -1

    const poll = async () => {
      try {
        const st = await analysisApi.status(videoId, ctrl.signal)
        if (!isActive(st.status) || st.progress !== lastProgress) {
          lastProgress = st.progress
          const d = await load(ctrl.signal)   // refresh so claims appear as they're verified
          if (d && !isActive(d.status.status)) return
        }
      } catch (e) {
        if (e.name === 'AbortError') return
      }
      timer.current = setTimeout(poll, POLL_MS)
    }

    setLoading(true)
    load(ctrl.signal).then((d) => { if (d && isActive(d.status.status)) timer.current = setTimeout(poll, POLL_MS) })
    return () => { ctrl.abort(); clearTimeout(timer.current) }
  }, [videoId, load, run])

  const retry = async () => {
    await analysisApi.retry(videoId)
    setRun((n) => n + 1) // restarts the polling effect
  }

  const recheck = async () => {
    await analysisApi.recheck(videoId)
    setRun((n) => n + 1)
  }

  return { data, error, loading, reload: load, retry, recheck }
}
