import { Link, Outlet } from 'react-router-dom'
import { useTheme } from '../../context/ThemeContext'

export function PublicLayout() {
  const { isDark, toggle } = useTheme()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 dark:border-slate-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link to="/" className="text-lg font-semibold text-brand-navy dark:text-white">
            TrustMesh
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={toggle}
              aria-label="Toggle dark mode"
              className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            >
              {isDark ? '☀️' : '🌙'}
            </button>
            <Link
              to="/login"
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="rounded-lg bg-brand-blue px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Sign up
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 px-4 py-6 text-center text-xs text-slate-400 dark:border-slate-800">
        Blockchain-AI Enhanced ONDC · Trust scoring, fraud detection, and dispute resolution for a decentralized
        commerce network.
      </footer>
    </div>
  )
}
