import { GitCompare, History, LayoutDashboard, LogOut, Menu, UserRound, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { Logo } from '../ui/index.jsx'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/history', label: 'History', icon: History },
  { to: '/compare', label: 'Compare videos', icon: GitCompare },
  { to: '/profile', label: 'Profile', icon: UserRound },
]

export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const links = (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} onClick={() => setOpen(false)}
          className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition
            ${isActive ? 'bg-navy-900 text-white' : 'text-navy-600 hover:bg-navy-50'}`}>
          <Icon className="h-4 w-4" /> {label}
        </NavLink>
      ))}
    </nav>
  )

  const footer = (
    <div className="border-t border-navy-100 pt-4">
      <div className="px-3 text-sm">
        <div className="font-semibold truncate">{user?.name}</div>
        <div className="text-navy-400 truncate text-xs">{user?.email}</div>
      </div>
      <button onClick={() => { logout(); navigate('/') }}
        className="mt-3 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-navy-600 hover:bg-navy-50">
        <LogOut className="h-4 w-4" /> Sign out
      </button>
    </div>
  )

  return (
    <div className="min-h-screen lg:flex">
      <aside className="hidden lg:flex w-64 shrink-0 flex-col justify-between border-r border-navy-100 bg-white px-4 py-6 sticky top-0 h-screen">
        <div className="space-y-8"><div className="px-2"><Logo to="/dashboard" /></div>{links}</div>
        {footer}
      </aside>

      <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between border-b border-navy-100 bg-white/90 backdrop-blur px-4 py-3">
        <Logo to="/dashboard" />
        <button aria-label="Open menu" onClick={() => setOpen(true)} className="rounded-lg p-2 hover:bg-navy-50"><Menu /></button>
      </header>
      {open && (
        <div className="lg:hidden fixed inset-0 z-40 bg-navy-950/30" onClick={() => setOpen(false)}>
          <div className="absolute right-0 top-0 h-full w-72 bg-white p-5 flex flex-col justify-between" onClick={(e) => e.stopPropagation()}>
            <div className="space-y-6">
              <div className="flex justify-end"><button aria-label="Close menu" onClick={() => setOpen(false)}><X /></button></div>
              {links}
            </div>
            {footer}
          </div>
        </div>
      )}

      <main className="flex-1 min-w-0 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}
