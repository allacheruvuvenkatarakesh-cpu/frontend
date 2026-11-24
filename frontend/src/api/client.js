// Minimal fetch wrapper: base URL, bearer token, JSON parsing and uniform errors.
const BASE = import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'lts_token'

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* storage unavailable */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* storage unavailable */ } },
}

export class ApiError extends Error {
  constructor(message, status, code, details) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export async function api(path, { method = 'GET', body, form, signal, auth = true } = {}) {
  const headers = {}
  const token = tokenStore.get()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) payload = form
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(`${BASE}/api${path}`, { method, headers, body: payload, signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError('Cannot reach the server. Check that the backend is running.', 0, 'network_error')
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && auth) onUnauthorized()
    const err = data?.error || {}
    throw new ApiError(err.message || `Request failed (${res.status})`, res.status, err.code, err.details)
  }
  return data
}

/** Upload with progress events (fetch has no upload progress, so use XHR). */
export function uploadWithProgress(path, form, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/api${path}`)
    const token = tokenStore.get()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100))
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch { /* empty */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new ApiError(data?.error?.message || `Upload failed (${xhr.status})`, xhr.status, data?.error?.code))
    }
    xhr.onerror = () => reject(new ApiError('Upload failed: network error', 0, 'network_error'))
    xhr.send(form)
  })
}

export const apiBase = BASE

/** Download an authenticated file (e.g. a PDF report) and save it with the given name. */
export async function downloadFile(path, filename) {
  const res = await fetch(`${BASE}/api${path}`, { headers: { Authorization: `Bearer ${tokenStore.get()}` } })
  if (!res.ok) throw new ApiError(`Download failed (${res.status})`, res.status, 'download_failed')
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
