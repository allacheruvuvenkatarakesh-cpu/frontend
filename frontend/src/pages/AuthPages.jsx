import { motion } from 'framer-motion'
import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button, ErrorBanner, Logo } from '../components/ui/index.jsx'
import { useAuth } from '../context/AuthContext.jsx'

function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-navy-900 p-12 text-white">
        <Logo light />
        <div>
          <h2 className="text-3xl font-extrabold leading-tight">Every verdict backed by evidence you can read yourself.</h2>
          <p className="mt-4 text-navy-200">Claims are checked against retrieved sources. When the evidence isn't there, we say so.</p>
        </div>
        <p className="text-xs text-navy-300">© LiveTruth Shield</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm">
          <div className="lg:hidden mb-8"><Logo /></div>
          <h1 className="text-2xl font-extrabold">{title}</h1>
          <p className="mt-1 text-sm text-navy-500">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 text-sm text-navy-500">{footer}</p>
        </motion.div>
      </div>
    </div>
  )
}

function useAuthForm(action) {
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const submit = async (e, ...args) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await action(...args)
      navigate(location.state?.from || '/dashboard', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }
  return { error, busy, submit }
}

export function LoginPage() {
  const { login, user } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { error, busy, submit } = useAuthForm(login)
  if (user) return <Navigate to="/dashboard" replace />
  return (
    <AuthShell title="Welcome back" subtitle="Sign in to continue your analyses."
      footer={<>No account? <Link to="/register" className="font-semibold text-navy-900 underline">Create one</Link></>}>
      <form onSubmit={(e) => submit(e, email, password)} className="space-y-4">
        <ErrorBanner error={error} />
        <div><label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" required autoComplete="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div><label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" required autoComplete="current-password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <Button type="submit" loading={busy} className="w-full py-3">Sign in</Button>
      </form>
    </AuthShell>
  )
}

export function RegisterPage() {
  const { register, user } = useAuth()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const { error, busy, submit } = useAuthForm(register)
  if (user) return <Navigate to="/dashboard" replace />
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  return (
    <AuthShell title="Create your account" subtitle="Start checking videos in under a minute."
      footer={<>Already have an account? <Link to="/login" className="font-semibold text-navy-900 underline">Sign in</Link></>}>
      <form onSubmit={(e) => submit(e, form.name, form.email, form.password)} className="space-y-4">
        <ErrorBanner error={error} />
        <div><label className="label" htmlFor="name">Name</label>
          <input id="name" required maxLength={80} autoComplete="name" className="input" value={form.name} onChange={set('name')} /></div>
        <div><label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" required autoComplete="email" className="input" value={form.email} onChange={set('email')} /></div>
        <div><label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" required minLength={8} autoComplete="new-password" className="input" value={form.password} onChange={set('password')} />
          <p className="mt-1 text-xs text-navy-400">At least 8 characters.</p></div>
        <Button type="submit" loading={busy} className="w-full py-3">Create account</Button>
      </form>
    </AuthShell>
  )
}
