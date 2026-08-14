import { useState, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'

interface NavItem {
  to: string
  label: string
}

const NAV_ITEMS: Record<'buyer' | 'seller' | 'admin', NavItem[]> = {
  buyer: [
    { to: '/buyer', label: 'Dashboard' },
    { to: '/buyer/products', label: 'Products' },
    { to: '/buyer/recommendations', label: 'Recommendations' },
    { to: '/buyer/orders', label: 'Orders' },
    { to: '/buyer/wishlist', label: 'Wishlist' },
    { to: '/buyer/fraud-alerts', label: 'Fraud Alerts' },
    { to: '/buyer/disputes', label: 'Disputes' },
    { to: '/buyer/settings', label: 'Settings' },
  ],
  seller: [
    { to: '/seller', label: 'Dashboard' },
    { to: '/seller/products', label: 'Products' },
    { to: '/seller/orders', label: 'Orders' },
    { to: '/seller/trust', label: 'Trust' },
    { to: '/seller/fraud-risk', label: 'Fraud Risk' },
    { to: '/seller/disputes', label: 'Disputes' },
    { to: '/seller/settings', label: 'Settings' },
  ],
  admin: [
    { to: '/admin', label: 'Analytics' },
    { to: '/admin/users', label: 'Users' },
    { to: '/admin/fraud', label: 'Fraud Dashboard' },
    { to: '/admin/disputes', label: 'Disputes' },
    { to: '/admin/trust', label: 'Trust Monitoring' },
    { to: '/admin/blockchain', label: 'Blockchain Explorer' },
    { to: '/admin/settings', label: 'Settings' },
  ],
}

function ThemeToggle() {
  const { isDark, toggle } = useTheme()
  return (
    <button
      onClick={toggle}
      aria-label="Toggle dark mode"
      className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
    >
      {isDark ? '☀️' : '🌙'}
    </button>
  )
}

export function DashboardLayout() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  if (!user) return null

  const items = NAV_ITEMS[user.role as 'buyer' | 'seller' | 'admin']

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label="Toggle navigation"
            >
              ☰
            </button>
            <NavLink to={`/${user.role}`} className="text-lg font-semibold text-brand-navy dark:text-white">
              TrustMesh
            </NavLink>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-slate-500 sm:inline dark:text-slate-400">
              {user.full_name} · <span className="capitalize">{user.role}</span>
            </span>
            <ThemeToggle />
            <button
              onClick={logout}
              className="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              Log out
            </button>
          </div>
        </div>
        <nav
          className={`mx-auto max-w-7xl flex-col gap-1 border-t border-slate-100 px-4 py-2 md:flex md:flex-row md:overflow-x-auto md:border-t-0 dark:border-slate-900 ${menuOpen ? 'flex' : 'hidden'}`}
        >
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === `/${user.role}`}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium ${
                  isActive
                    ? 'bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

function Footer(): ReactNode {
  return (
    <footer className="border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-400 dark:border-slate-800">
      Blockchain-AI Enhanced ONDC · demo project
    </footer>
  )
}
