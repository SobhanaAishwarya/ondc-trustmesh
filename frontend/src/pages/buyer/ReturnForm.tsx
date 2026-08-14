import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { requestReturn } from '../../api/orders'
import { Button, ErrorBanner, Select, TextArea } from '../../components/ui'
import { apiErrorMessage } from '../../api/client'
import { DISPUTE_REASONS } from '../../lib/constants'
import type { DisputeReason } from '../../types'

const ITEM_CONDITIONS = [
  { value: 'good', label: 'Good — unopened / as described' },
  { value: 'damaged', label: 'Damaged' },
  { value: 'missing_parts', label: 'Missing parts' },
] as const

export function ReturnForm({ orderId, onDone }: { orderId: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [reason, setReason] = useState<DisputeReason>('item_not_as_described')
  const [itemCondition, setItemCondition] = useState<'good' | 'damaged' | 'missing_parts'>('good')
  const [description, setDescription] = useState('')

  const mutation = useMutation({
    mutationFn: () => requestReturn(orderId, { reason, description, item_condition: itemCondition }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      queryClient.invalidateQueries({ queryKey: ['disputes'] })
      onDone()
    },
  })

  return (
    <div className="mt-3 space-y-3 border-t border-slate-100 pt-3 dark:border-slate-800">
      {mutation.error && <ErrorBanner message={apiErrorMessage(mutation.error, 'Could not request return')} />}
      {mutation.isSuccess && (
        <p className="text-sm text-status-good">
          {mutation.data.status === 'auto_resolved'
            ? 'Return approved — refund initiated automatically.'
            : 'Return submitted for review — the seller will respond.'}
        </p>
      )}
      <Select value={reason} onChange={(e) => setReason(e.target.value as DisputeReason)}>
        {DISPUTE_REASONS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </Select>
      <Select value={itemCondition} onChange={(e) => setItemCondition(e.target.value as typeof itemCondition)}>
        {ITEM_CONDITIONS.map((c) => (
          <option key={c.value} value={c.value}>
            {c.label}
          </option>
        ))}
      </Select>
      <p className="text-xs text-slate-400">
        {itemCondition === 'good'
          ? 'Good-condition returns within the 7-day window are refunded automatically, no seller review needed.'
          : "A damaged/incomplete return opens a case the seller can respond to, rather than an automatic refund."}
      </p>
      <TextArea
        placeholder="Anything else worth mentioning..."
        rows={2}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <div className="flex gap-2">
        <Button isLoading={mutation.isPending} onClick={() => mutation.mutate()} disabled={mutation.isSuccess}>
          Submit return
        </Button>
        <Button variant="ghost" onClick={onDone}>
          {mutation.isSuccess ? 'Close' : 'Cancel'}
        </Button>
      </div>
    </div>
  )
}
