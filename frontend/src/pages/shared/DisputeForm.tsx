import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { raiseDispute } from '../../api/disputes'
import { Button, ErrorBanner, Select, TextArea } from '../../components/ui'
import { apiErrorMessage } from '../../api/client'
import { DISPUTE_REASONS } from '../../lib/constants'
import type { DisputeReason } from '../../types'

export function DisputeForm({ orderId, onDone }: { orderId: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [reason, setReason] = useState<DisputeReason>('item_not_received')
  const [description, setDescription] = useState('')
  const [evidenceScore, setEvidenceScore] = useState(0.5)

  const mutation = useMutation({
    mutationFn: () => raiseDispute({ order_id: orderId, reason, description, evidence_score: String(evidenceScore) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      queryClient.invalidateQueries({ queryKey: ['disputes'] })
      onDone()
    },
  })

  return (
    <div className="mt-3 space-y-3 border-t border-slate-100 pt-3 dark:border-slate-800">
      {mutation.error && <ErrorBanner message={apiErrorMessage(mutation.error, 'Could not raise dispute')} />}
      <Select value={reason} onChange={(e) => setReason(e.target.value as DisputeReason)}>
        {DISPUTE_REASONS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </Select>
      <TextArea
        placeholder="Describe what happened..."
        rows={2}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <div>
        <label className="mb-1 block text-xs text-slate-500 dark:text-slate-400">
          How confident are you in your case? {Math.round(evidenceScore * 100)}%
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={evidenceScore}
          onChange={(e) => setEvidenceScore(Number(e.target.value))}
          className="w-full"
        />
      </div>
      <div className="flex gap-2">
        <Button isLoading={mutation.isPending} onClick={() => mutation.mutate()}>
          Submit dispute
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
