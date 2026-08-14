import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listWishlist, removeFromWishlist } from '../../api/wishlist'
import { Button, Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { formatCurrency } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'

export function WishlistPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({ queryKey: ['wishlist'], queryFn: listWishlist })

  const removeMutation = useMutation({
    mutationFn: (productId: string) => removeFromWishlist(productId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['wishlist'] }),
  })

  return (
    <div>
      <PageHeader title="Wishlist" description="Products you've saved for later." />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load wishlist')} />}
      {data && data.length === 0 && <EmptyState title="Your wishlist is empty" description="Save products while browsing." />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.map((item) => (
          <Card key={item.id} className="p-4">
            <Link to={`/buyer/products/${item.product.id}`}>
              <p className="text-xs font-medium text-brand-blue">{item.product.category}</p>
              <h3 className="mt-1 font-semibold hover:underline">{item.product.name}</h3>
              <p className="mt-2 font-semibold">{formatCurrency(item.product.price)}</p>
            </Link>
            <Button
              variant="secondary"
              className="mt-3 w-full"
              isLoading={removeMutation.isPending}
              onClick={() => removeMutation.mutate(item.product.id)}
            >
              Remove
            </Button>
          </Card>
        ))}
      </div>
    </div>
  )
}
