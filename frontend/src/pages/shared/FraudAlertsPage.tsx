import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listFraudAlerts, reviewFraudLog } from '../../api/fraud'
import { useAuth } from '../../context/AuthContext'
import { Badge, Button, Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { formatDate, titleCase } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'

export function FraudAlertsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [onlyFlagged, setOnlyFlagged] = useState(true)

  const { data, isLoading, error } = useQuery({
    queryKey: ['fraud-alerts', onlyFlagged],
    queryFn: () => listFraudAlerts(onlyFlagged, 50),
  })

  const reviewMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: 'confirmed_fraud' | 'false_positive' }) =>
      reviewFraudLog(id, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['fraud-alerts'] }),
  })

  return (
    <div>
      <PageHeader
        title="Fraud alerts"
        description={
          user?.role === 'admin'
            ? 'Every scored transaction across the network. Review flagged ones to confirm or dismiss.'
            : 'Transactions on your account that the fraud model has scored.'
        }
        action={
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} />
            Only flagged
          </label>
        }
      />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load fraud alerts')} />}
      {data && data.items.length === 0 && <EmptyState title="No fraud logs" description="Nothing matches this filter yet." />}

      <div className="space-y-3">
        {data?.items.map((log) => (
          <Card key={log.id} className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  {log.is_flagged ? <Badge tone="critical">Flagged</Badge> : <Badge tone="good">Clear</Badge>}
                  <span className="text-sm font-medium">{(Number(log.fraud_probability) * 100).toFixed(1)}% fraud probability</span>
                </div>
                <p className="mt-1 text-xs text-slate-400">{formatDate(log.created_at)} · {log.model_name}</p>
              </div>
              {log.admin_decision && (
                <Badge tone={log.admin_decision === 'confirmed_fraud' ? 'critical' : 'good'}>
                  {titleCase(log.admin_decision)}
                </Badge>
              )}
            </div>
            {log.risk_factors && (
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(log.risk_factors).map(([name, info]) => (
                  <span key={name} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {titleCase(name)}: {String(info.value)}
                  </span>
                ))}
              </div>
            )}
            {user?.role === 'admin' && log.is_flagged && !log.admin_decision && (
              <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
                <Button
                  variant="danger"
                  isLoading={reviewMutation.isPending}
                  onClick={() => reviewMutation.mutate({ id: log.id, decision: 'confirmed_fraud' })}
                >
                  Confirm fraud
                </Button>
                <Button
                  variant="secondary"
                  isLoading={reviewMutation.isPending}
                  onClick={() => reviewMutation.mutate({ id: log.id, decision: 'false_positive' })}
                >
                  False positive
                </Button>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
