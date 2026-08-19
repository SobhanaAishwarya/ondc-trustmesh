import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { roleHomePath } from '../api/auth'
import { apiErrorMessage } from '../api/client'
import { Button, Card, ErrorBanner, Input, Label } from '../components/ui'
import { WalletConnectButton } from '../components/WalletConnectButton'

export function LoginPage() {
  const { login, loginWithWallet } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const me = await login(email, password)
      navigate(roleHomePath(me.role))
    } catch (err) {
      setError(apiErrorMessage(err, 'Login failed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleWalletSignIn(address: string, signature: string) {
    const me = await loginWithWallet(address, signature)
    navigate(roleHomePath(me.role))
  }

  return (
    <div className="mx-auto flex max-w-md flex-col justify-center px-4 py-16">
      <Card className="p-8">
        <h1 className="text-xl font-semibold">Log in</h1>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {error && <ErrorBanner message={error} />}
          <div>
            <Label>Email</Label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
          </div>
          <div>
            <Label>Password</Label>
            <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <Button type="submit" className="w-full" isLoading={isSubmitting}>
            Log in
          </Button>
        </form>

        <div className="my-4 flex items-center gap-3 text-xs text-slate-400">
          <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
          or
          <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
        </div>
        <WalletConnectButton label="Sign in with wallet" onSigned={handleWalletSignIn} />
        <p className="mt-2 text-center text-xs text-slate-400">
          Only works if you've already linked a wallet to your account in Settings.
        </p>

        <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
          No account?{' '}
          <Link to="/signup" className="font-medium text-brand-blue">
            Sign up
          </Link>
        </p>
      </Card>
    </div>
  )
}
