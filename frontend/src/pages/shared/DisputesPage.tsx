import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { arbitrateDispute, listDisputes, submitEvidence } from '../../api/disputes'
import { useAuth } from '../../context/AuthContext'
import { Button, Card, EmptyState, ErrorBanner, Input, LoadingBlock, PageHeader } from '../../components/ui'
import { DisputeStatusBadge } from '../../components/domain'
import { formatDate, titleCase } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'
import type { Dispute } from '../../types'

const OPEN_STATUSES = ['open', 'under_review']

function EvidencePanel({ dispute }: { dispute: Dispute }) {
  const queryClient = useQueryClient()
  const [score, setScore] = useState(0.5)
  const mutation = useMutation({
    mutationFn: () => submitEvidence(dispute.id, String(score)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['disputes'] }),
  })

  return (
    <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
      {mutation.error && (
        <div className="mb-2">
          <ErrorBanner message={apiErrorMessage(mutation.error, 'Could not submit evidence')} />
        </div>
      )}
      <label className="mb-1 block text-xs text-slate-500 dark:text-slate-400">
        Your evidence confidence: {Math.round(score * 100)}%
      </label>
      <div className="flex items-center gap-3">
        <input type="range" min={0} max={1} step={0.05} value={score} onChange={(e) => setScore(Number(e.target.value))} className="flex-1" />
        <Button isLoading={mutation.isPending} onClick={() => mutation.mutate()}>
          Submit evidence
        </Button>
      </div>
    </div>
  )
}

function ArbitratePanel({ dispute }: { dispute: Dispute }) {
  const queryClient = useQueryClient()
  const [sellerShare, setSellerShare] = useState(50)
  const mutation = useMutation({
    mutationFn: () => arbitrateDispute(dispute.id, Math.round(sellerShare * 100)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['disputes'] }),
  })

  return (
    <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
      {mutation.error && (
        <div className="mb-2">
          <ErrorBanner message={apiErrorMessage(mutation.error, 'Could not arbitrate')} />
        </div>
      )}
      <label className="mb-1 block text-xs text-slate-500 dark:text-slate-400">Seller share: {sellerShare}%</label>
      <div className="flex items-center gap-3">
        <Input
          type="number"
          min={0}
          max={100}
          value={sellerShare}
          onChange={(e) => setSellerShare(Number(e.target.value))}
          className="w-24"
        />
        <Button isLoading={mutation.isPending} onClick={() => mutation.mutate()}>
          Arbitrate
        </Button>
      </div>
    </div>
  )
}

export function DisputesPage() {
  const { user } = useAuth()
  const { data, isLoading, error } = useQuery({ queryKey: ['disputes'], queryFn: () => listDisputes(50) })

  return (
    <div>
      <PageHeader
        title="Disputes"
        description="Raised on a delivered/shipped order, auto-resolved once both parties submit evidence, or overridden by an admin."
      />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load disputes')} />}
      {data && data.items.length === 0 && <EmptyState title="No disputes" description="Nothing to see here." />}

      <div className="space-y-3">
        {data?.items.map((dispute) => (
          <Card key={dispute.id} className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium">{titleCase(dispute.reason)}</p>
                <p className="mt-1 text-xs text-slate-400">{formatDate(dispute.created_at)}</p>
              </div>
              <DisputeStatusBadge status={dispute.status} />
            </div>
            {dispute.description && <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{dispute.description}</p>}
            {dispute.resolution_outcome && (
              <p className="mt-2 text-sm font-medium text-brand-blue">
                Outcome: {dispute.resolution_outcome} ({(dispute.seller_share_bps ?? 0) / 100}% to seller)
              </p>
            )}
            {(user?.role === 'buyer' || user?.role === 'seller') && OPEN_STATUSES.includes(dispute.status) && (
              <EvidencePanel dispute={dispute} />
            )}
            {user?.role === 'admin' && OPEN_STATUSES.includes(dispute.status) && <ArbitratePanel dispute={dispute} />}
          </Card>
        ))}
      </div>
    </div>
  )
}
