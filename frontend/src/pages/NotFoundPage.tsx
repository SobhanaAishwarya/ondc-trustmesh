import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-3xl font-bold">404</h1>
      <p className="text-slate-500 dark:text-slate-400">This page doesn't exist.</p>
      <Link to="/" className="font-medium text-brand-blue">
        Back home
      </Link>
    </div>
  )
}
