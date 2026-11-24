import { UserRound } from 'lucide-react'
import { useState } from 'react'
import { Button, ErrorBanner } from '../components/ui/index.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDate, LANGUAGES } from '../utils/format.js'

export default function ProfilePage() {
  const { user, updateProfile } = useAuth()
  const [name, setName] = useState(user?.name || '')
  const [lang, setLang] = useState(user?.preferred_language || 'en')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  const save = async (e) => {
    e.preventDefault()
    setBusy(true); setSaved(false); setError(null)
    try { await updateProfile({ name: name.trim(), preferred_language: lang }); setSaved(true) } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="flex items-center gap-2 text-2xl font-extrabold"><UserRound className="h-6 w-6" />Profile</h1>
      <form onSubmit={save} className="card space-y-4 p-6">
        <div><label className="label" htmlFor="pname">Name</label>
          <input id="pname" className="input" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div><span className="label">Email</span><p className="text-sm text-navy-600">{user?.email}</p></div>
        <div><label className="label" htmlFor="plang">Results language</label>
          <select id="plang" className="input" value={lang} onChange={(e) => setLang(e.target.value)}>
            {Object.entries(LANGUAGES).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
          <p className="mt-1 text-xs text-navy-400">Claims and explanations are shown in this language, with the original alongside.</p></div>
        <p className="text-xs text-navy-400">Member since {formatDate(user?.created_at)}</p>
        <ErrorBanner error={error} />
        {saved && <p className="text-sm text-green-700" role="status">Saved.</p>}
        <Button type="submit" loading={busy}>Save changes</Button>
      </form>
    </div>
  )
}
