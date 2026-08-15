import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listWishlist, removeFromWishlist } from '../../api/wishlist'
import { Button, Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { ProductImage } from '../../components/domain'
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
          <Card key={item.id} className="overflow-hidden p-0">
            <Link to={`/buyer/products/${item.product.id}`}>
              <ProductImage src={item.product.image_url} alt={item.product.name} className="h-32 w-full" />
              <div className="p-4">
                <p className="text-xs font-medium text-brand-blue">{item.product.category}</p>
                <h3 className="mt-1 font-semibold hover:underline">{item.product.name}</h3>
                <p className="mt-2 font-semibold">{formatCurrency(item.product.price)}</p>
              </div>
            </Link>
            <div className="px-4 pb-4">
              <Button
                variant="secondary"
                className="w-full"
                isLoading={removeMutation.isPending}
                onClick={() => removeMutation.mutate(item.product.id)}
              >
                Remove
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
