import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../context/AuthContext'
import { LoginPage } from './LoginPage'
import * as authApi from '../api/auth'

const navigate = vi.fn()
vi.mock('react-router-dom', async (importActual) => {
  const actual = await importActual<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigate }
})

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function fields() {
  const [email, password] = screen.getAllByDisplayValue('') as HTMLInputElement[]
  return { email, password }
}

beforeEach(() => {
  localStorage.clear()
  navigate.mockClear()
  vi.restoreAllMocks()
})

describe('LoginPage', () => {
  it('renders the login form', () => {
    renderLoginPage()
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign up' })).toBeInTheDocument()
  })

  it('logs in and routes to the role-appropriate home on success', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'a', refresh_token: 'r', token_type: 'bearer', role: 'buyer', user_id: 'u1',
    })
    vi.spyOn(authApi, 'fetchMe').mockResolvedValue({
      id: 'u1', email: 'buyer@example.com', full_name: 'Test Buyer', role: 'buyer',
    } as never)
    const user = userEvent.setup()
    renderLoginPage()
    const { email, password } = fields()

    await user.type(email, 'buyer@example.com')
    await user.type(password, 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/buyer'))
    expect(localStorage.getItem('ondc_access_token')).toBe('a')
  })

  it('shows an error banner instead of navigating when login fails', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue(new Error('invalid credentials'))
    const user = userEvent.setup()
    renderLoginPage()
    const { email, password } = fields()

    await user.type(email, 'buyer@example.com')
    await user.type(password, 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Login failed')).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
  })
})
