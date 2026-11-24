import { api, uploadWithProgress } from './client.js'

export const authApi = {
  register: (data) => api('/auth/register', { method: 'POST', body: data, auth: false }),
  login: (data) => api('/auth/login', { method: 'POST', body: data, auth: false }),
  me: () => api('/auth/me'),
  updateMe: (data) => api('/auth/me', { method: 'PATCH', body: data }),
}

export const videoApi = {
  submitUrl: (url, title) => api('/videos/url', { method: 'POST', body: { url, title: title || null } }),
  upload: (file, title, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    if (title) form.append('title', title)
    return uploadWithProgress('/videos/upload', form, onProgress)
  },
  mediaToken: (videoId) => api(`/videos/${videoId}/media-token`),
}

export const analysisApi = {
  list: ({ page = 1, pageSize = 10, status, q } = {}) => {
    const p = new URLSearchParams({ page, page_size: pageSize })
    if (status) p.set('status', status)
    if (q) p.set('q', q)
    return api(`/analyses?${p}`)
  },
  stats: () => api('/analyses/stats'),
  get: (videoId, signal) => api(`/analyses/${videoId}`, { signal }),
  status: (videoId, signal) => api(`/analyses/${videoId}/status`, { signal }),
  retry: (videoId) => api(`/analyses/${videoId}/retry`, { method: 'POST' }),
  recheck: (videoId) => api(`/analyses/${videoId}/recheck`, { method: 'POST' }),
  translation: (videoId, lang) => api(`/analyses/${videoId}/translation?lang=${lang}`),
  remove: (videoId) => api(`/analyses/${videoId}`, { method: 'DELETE' }),
}

export const fingerprintApi = {
  get: (videoId) => api(`/analyses/${videoId}/fingerprint`),
  byId: (fingerprintId) => api(`/fingerprints/${encodeURIComponent(fingerprintId)}`),
  compare: (a, b) => api(`/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  candidates: (videoId) => api(`/compare/candidates?video_id=${encodeURIComponent(videoId)}`),
}

export const featureApi = {
  authenticity: (videoId) => api(`/deepfake/${videoId}`),
  startAuthenticity: (videoId) => api('/deepfake/analyse', { method: 'POST', body: { video_id: videoId } }),
  graph: (videoId) => api(`/evidence-graph/${videoId}`),
  generateReport: (videoId) => api('/reports/generate', { method: 'POST', body: { video_id: videoId } }),
  checkClaim: (claim) => api('/verification/check', { method: 'POST', body: { claim } }),
}
