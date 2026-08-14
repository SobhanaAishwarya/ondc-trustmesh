import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { roleHomePath } from '../api/auth'
import { apiErrorMessage } from '../api/client'
import { Button, Card, ErrorBanner, Input, Label, Select } from '../components/ui'
import { CATEGORIES, CITIES } from '../lib/constants'

type Role = 'buyer' | 'seller'

export function SignupPage() {
  const { registerBuyer, registerSeller } = useAuth()
  const navigate = useNavigate()
  const [role, setRole] = useState<Role>('buyer')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [businessName, setBusinessName] = useState('')
  const [preferredCategories, setPreferredCategories] = useState<string[]>([])
  const [city, setCity] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function toggleCategory(category: string) {
    setPreferredCategories((prev) =>
      prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category],
    )
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const me =
        role === 'buyer'
          ? await registerBuyer({
              email,
              password,
              full_name: fullName,
              preferred_categories: preferredCategories,
              city: city || undefined,
            })
          : await registerSeller({
              email,
              password,
              full_name: fullName,
              business_name: businessName,
              city: city || undefined,
            })
      navigate(roleHomePath(me.role))
    } catch (err) {
      setError(apiErrorMessage(err, 'Sign up failed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col justify-center px-4 py-16">
      <Card className="p-8">
        <h1 className="text-xl font-semibold">Create an account</h1>

        <div className="mt-4 grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
          {(['buyer', 'seller'] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRole(r)}
              className={`rounded-md py-1.5 text-sm font-medium capitalize transition ${
                role === r ? 'bg-white shadow dark:bg-slate-700' : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {error && <ErrorBanner message={error} />}
          <div>
            <Label>Full name</Label>
            <Input required value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div>
            <Label>Email</Label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <Label>Password</Label>
            <Input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>

          {role === 'seller' ? (
            <div>
              <Label>Business name</Label>
              <Input required value={businessName} onChange={(e) => setBusinessName(e.target.value)} />
            </div>
          ) : (
            <div>
              <Label>Preferred categories (optional)</Label>
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

          <div>
            <Label>City (optional)</Label>
            <Select value={city} onChange={(e) => setCity(e.target.value)}>
              <option value="">Not set</option>
              {CITIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-slate-400">
              {role === 'seller'
                ? 'Used to rank you higher for nearby buyers in their recommendations.'
                : "Used to favor nearby, faster-shipping sellers in your recommendations."}
            </p>
          </div>

          <Button type="submit" className="w-full" isLoading={isSubmitting}>
            Create account
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand-blue">
            Log in
          </Link>
        </p>
      </Card>
    </div>
  )
}
