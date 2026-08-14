import { useState, type FormEvent } from 'react'
import { useAuth } from '../../context/AuthContext'
import { updateMe } from '../../api/auth'
import { apiErrorMessage } from '../../api/client'
import { Button, Card, ErrorBanner, Input, Label, PageHeader, Select } from '../../components/ui'
import { CATEGORIES, CITIES } from '../../lib/constants'

export function SettingsPage() {
  const { user, refreshUser } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [walletAddress, setWalletAddress] = useState(user?.buyer?.wallet_address ?? user?.seller?.wallet_address ?? '')
  const [businessName, setBusinessName] = useState(user?.seller?.business_name ?? '')
  const [gstin, setGstin] = useState(user?.seller?.gstin ?? '')
  const [preferredCategories, setPreferredCategories] = useState<string[]>(user?.buyer?.preferred_categories ?? [])
  const [city, setCity] = useState(user?.buyer?.city ?? user?.seller?.city ?? '')
  const [deliveryRadiusKm, setDeliveryRadiusKm] = useState(String(user?.seller?.delivery_radius_km ?? 50))
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!user) return null

  function toggleCategory(category: string) {
    setPreferredCategories((prev) => (prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    setIsSubmitting(true)
    try {
      await updateMe({
        full_name: fullName,
        phone: phone || undefined,
        wallet_address: walletAddress || undefined,
        city: city || undefined,
        ...(user!.role === 'buyer' ? { preferred_categories: preferredCategories } : {}),
        ...(user!.role === 'seller'
          ? { business_name: businessName, gstin: gstin || undefined, delivery_radius_km: Number(deliveryRadiusKm) }
          : {}),
      })
      await refreshUser()
      setSuccess(true)
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not update profile'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title="Settings" description="Update your profile." />
      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <ErrorBanner message={error} />}
          {success && <p className="text-sm text-status-good">Profile updated.</p>}
          <div>
            <Label>Full name</Label>
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div>
            <Label>Phone</Label>
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <div>
            <Label>Wallet address</Label>
            <Input
              value={walletAddress}
              onChange={(e) => setWalletAddress(e.target.value)}
              placeholder="0x..."
            />
            {user.role === 'seller' && (
              <p className="mt-1 text-xs text-slate-400">
                Setting this registers you on the on-chain TrustScore ledger (if the blockchain bridge is enabled).
                {user.seller?.is_onchain_registered ? ' Currently registered on-chain.' : ' Not yet registered on-chain.'}
              </p>
            )}
          </div>

          {user.role === 'seller' && (
            <>
              <div>
                <Label>Business name</Label>
                <Input value={businessName} onChange={(e) => setBusinessName(e.target.value)} />
              </div>
              <div>
                <Label>GSTIN</Label>
                <Input value={gstin} onChange={(e) => setGstin(e.target.value)} />
              </div>
              <div>
                <Label>Delivery radius (km)</Label>
                <Input
                  type="number"
                  min={1}
                  max={5000}
                  value={deliveryRadiusKm}
                  onChange={(e) => setDeliveryRadiusKm(e.target.value)}
                />
                <p className="mt-1 text-xs text-slate-400">
                  How far you ship — sellers ranked more competitively for buyers within this radius of your city.
                </p>
              </div>
            </>
          )}

          <div>
            <Label>City</Label>
            <Select value={city} onChange={(e) => setCity(e.target.value)}>
              <option value="">Not set</option>
              {CITIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-slate-400">
              {user.role === 'seller'
                ? 'Used to rank you higher for nearby buyers in their recommendations.'
                : 'Used to favor nearby, faster-shipping sellers in your recommendations.'}
            </p>
          </div>

          {user.role === 'buyer' && (
            <div>
              <Label>Preferred categories</Label>
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((category) => (
                  <button
                    type="button"
                    key={category}
                    onClick={() => toggleCategory(category)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      preferredCategories.includes(category)
                        ? 'border-brand-blue bg-brand-blue/10 text-brand-blue'
                        : 'border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>
          )}

          <Button type="submit" isLoading={isSubmitting}>
            Save changes
          </Button>
        </form>
      </Card>
    </div>
  )
}
