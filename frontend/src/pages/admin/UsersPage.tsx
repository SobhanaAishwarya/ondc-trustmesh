import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listUsers, setUserStatus } from '../../api/admin'
import { Badge, Button, Card, ErrorBanner, Input, LoadingBlock, PageHeader, Select } from '../../components/ui'
import { formatDate } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'
import type { UserRole } from '../../types'

export function UsersPage() {
  const [q, setQ] = useState('')
  const [role, setRole] = useState<UserRole | ''>('')
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-users', { q, role }],
    queryFn: () => listUsers({ q: q || undefined, role: role || undefined, limit: 50 }),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) => setUserStatus(id, isActive),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  return (
    <div>
      <PageHeader title="Users" description="Search, filter, and activate/deactivate accounts." />

      <div className="mb-4 flex flex-wrap gap-3">
        <Input placeholder="Search by name or email..." value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={role} onChange={(e) => setRole(e.target.value as UserRole | '')} className="max-w-xs">
          <option value="">All roles</option>
          <option value="buyer">Buyer</option>
          <option value="seller">Seller</option>
          <option value="admin">Admin</option>
        </Select>
      </div>

      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load users')} />}
      {statusMutation.error && <ErrorBanner message={apiErrorMessage(statusMutation.error, 'Could not update user')} />}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs tracking-wide text-slate-500 uppercase dark:border-slate-800 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Joined</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {data?.items.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-3">{u.full_name}</td>
                <td className="px-4 py-3 text-slate-500 dark:text-slate-400">{u.email}</td>
                <td className="px-4 py-3 capitalize">{u.role}</td>
                <td className="px-4 py-3">
                  {u.is_active ? <Badge tone="good">Active</Badge> : <Badge tone="critical">Deactivated</Badge>}
                </td>
                <td className="px-4 py-3 text-slate-400">{formatDate(u.created_at)}</td>
                <td className="px-4 py-3">
                  <Button
                    variant={u.is_active ? 'danger' : 'secondary'}
                    isLoading={statusMutation.isPending}
                    onClick={() => statusMutation.mutate({ id: u.id, isActive: !u.is_active })}
                  >
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
