import { useState } from 'react'
import { Button, ErrorBanner } from './ui'
import { connectWallet, signMessage } from '../lib/wallet'
import { getWalletNonce } from '../api/auth'
import { apiErrorMessage } from '../api/client'

/** Drives the full connect -> request a nonce -> sign -> hand off flow.
 * Used for both "link this wallet to my account" (Settings) and "sign in
 * with wallet" (Login) — the only difference is what `onSigned` does with
 * the resulting (address, signature) pair. */
export function WalletConnectButton({
  label,
  onSigned,
}: {
  label: string
  onSigned: (address: string, signature: string) => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)

  async function handleClick() {
    setError(null)
    setIsBusy(true)
    try {
      const address = await connectWallet()
      const message = await getWalletNonce(address)
      const signature = await signMessage(address, message)
      await onSigned(address, signature)
    } catch (err) {
      const fallback = err instanceof Error ? err.message : 'Wallet sign-in failed'
      setError(apiErrorMessage(err, fallback))
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <div>
      {error && <ErrorBanner message={error} />}
      <Button type="button" variant="secondary" className="mt-2 w-full" isLoading={isBusy} onClick={handleClick}>
        {label}
      </Button>
    </div>
  )
}
