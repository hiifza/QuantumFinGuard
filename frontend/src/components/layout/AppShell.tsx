import { useState, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'

interface NavItem {
  label: string
  path: string
  group: string
  built: boolean
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Executive Overview', path: '/overview', group: 'Overview', built: true },
  { label: 'Transactions', path: '/transactions', group: 'Overview', built: true },

  { label: 'Fraud & Risk', path: '/fraud', group: 'Intelligence', built: false },
  { label: 'Behavioral Intelligence', path: '/behavioral', group: 'Intelligence', built: false },

  { label: 'Investigation Workspace', path: '/investigation', group: 'Investigation', built: true },
  { label: 'Blockchain Explorer', path: '/blockchain', group: 'Investigation', built: false },
  { label: 'AI Investigation Copilot', path: '/copilot', group: 'Investigation', built: false },

  { label: 'Security Center', path: '/security', group: 'Security', built: false },
  { label: 'Quantum-Safe Security', path: '/security/pqc', group: 'Security', built: false },
  { label: 'Audit Trail', path: '/security/audit', group: 'Security', built: false },

  { label: 'Dataset Status', path: '/data', group: 'System', built: false },
]

const GROUPS = ['Overview', 'Intelligence', 'Investigation', 'Security', 'System']

function BrandMark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-[19px] w-[19px] flex-shrink-0">
      <circle cx="12" cy="12" r="9" stroke="var(--emerald)" strokeWidth="1.4" />
      <circle cx="12" cy="12" r="2.4" fill="var(--amber)" />
    </svg>
  )
}

function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (document.body.getAttribute('data-theme') as 'dark' | 'light') || 'dark',
  )
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.body.setAttribute('data-theme', next)
    setTheme(next)
  }
  return (
    <button
      onClick={toggle}
      title="Toggle theme"
      className="flex h-8 w-8 items-center justify-center rounded-md border transition-colors"
      style={{ borderColor: 'var(--line)', background: 'var(--surface)' }}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4">
        <circle cx="12" cy="12" r="4.5" />
        <path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
      </svg>
    </button>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="flex flex-col border-r p-4" style={{ background: 'var(--surface)', borderColor: 'var(--line)' }}>
        <div className="mb-7 flex items-center gap-2 px-2 pt-1 text-[14.5px] font-semibold">
          <BrandMark />
          QuantumFinGuard
        </div>

        <nav className="flex-1 overflow-y-auto">
          {GROUPS.map((group) => (
            <div key={group} className="mb-5">
              <div className="mb-2 px-2.5 text-[10px] tracking-wider" style={{ color: 'var(--text-dim)' }}>
                {group}
              </div>
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `mb-0.5 flex items-center justify-between rounded-[9px] px-2.5 py-2 text-[13.5px] transition-colors ${
                      isActive ? 'font-semibold' : ''
                    }`
                  }
                  style={({ isActive }) => ({
                    color: isActive ? 'var(--emerald)' : 'var(--text-dim)',
                    background: isActive ? 'var(--emerald-soft)' : 'transparent',
                  })}
                >
                  <span>{item.label}</span>
                  {!item.built && (
                    <span
                      className="rounded-full px-1.5 py-0.5 text-[9px]"
                      style={{ background: 'var(--surface-2)', color: 'var(--text-dim)' }}
                    >
                      soon
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="mt-auto border-t pt-3" style={{ borderColor: 'var(--line)' }}>
          <div className="flex items-center gap-2.5 rounded-[9px] p-2">
            <div
              className="h-7 w-7 flex-shrink-0 rounded-full"
              style={{ background: 'linear-gradient(135deg, var(--emerald), var(--amber))' }}
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[12.5px] font-semibold">{user?.full_name}</div>
              <div className="truncate text-[11px]" style={{ color: 'var(--text-dim)' }}>
                {user?.role}
              </div>
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md transition-colors"
              style={{ color: 'var(--text-dim)' }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <path d="M16 17l5-5-5-5M21 12H9" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      <div className="flex flex-col">
        <header
          className="flex items-center justify-end gap-3 border-b px-6 py-3"
          style={{ borderColor: 'var(--line)', background: 'var(--bg)' }}
        >
          <ThemeToggle />
        </header>
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
    </div>
  )
}
