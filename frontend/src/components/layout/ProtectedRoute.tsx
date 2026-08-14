import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { roleHomePath } from '../../api/auth'
import { LoadingBlock } from '../ui'
import type { UserRole } from '../../types'

export function ProtectedRoute({ allow }: { allow: UserRole[] }) {
  const { user, isLoading } = useAuth()

  if (isLoading) return <LoadingBlock />
  if (!user) return <Navigate to="/login" replace />
  if (!allow.includes(user.role)) return <Navigate to={roleHomePath(user.role)} replace />

  return <Outlet />
}
