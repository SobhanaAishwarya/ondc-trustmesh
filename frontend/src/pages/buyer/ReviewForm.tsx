import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createReview } from '../../api/reviews'
import { Button, ErrorBanner, TextArea } from '../../components/ui'
import { apiErrorMessage } from '../../api/client'

export function ReviewForm({ orderId, onDone }: { orderId: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')

  const mutation = useMutation({
    mutationFn: () => createReview(orderId, rating, comment || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      onDone()
    },
  })

  return (
    <div className="mt-3 space-y-3 border-t border-slate-100 pt-3 dark:border-slate-800">
      {mutation.error && <ErrorBanner message={apiErrorMessage(mutation.error, 'Could not submit review')} />}
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            onClick={() => setRating(star)}
            className={`text-2xl ${star <= rating ? 'text-brand-yellow' : 'text-slate-300 dark:text-slate-700'}`}
            aria-label={`${star} star`}
          >
            ★
          </button>
        ))}
      </div>
      <TextArea placeholder="Optional comment..." rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
      <div className="flex gap-2">
        <Button isLoading={mutation.isPending} onClick={() => mutation.mutate()}>
          Submit review
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
