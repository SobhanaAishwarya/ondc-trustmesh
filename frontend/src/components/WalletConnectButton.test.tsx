import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WalletConnectButton } from './WalletConnectButton'
import * as authApi from '../api/auth'

const ADDRESS = '0x90F79bf6EB2c4f870365E785982E1f101E93b906'

function installFakeWallet(overrides: Partial<Record<string, (...args: unknown[]) => unknown>> = {}) {
  const request = vi.fn(async ({ method }: { method: string }) => {
    if (overrides[method]) return overrides[method]()
    if (method === 'eth_requestAccounts') return [ADDRESS]
    if (method === 'personal_sign') return '0xdeadbeef'
    throw new Error(`unexpected method: ${method}`)
  })
  window.ethereum = { request }
  return request
}

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  window.ethereum = undefined
})

describe('WalletConnectButton', () => {
  it('walks connect -> nonce -> sign -> onSigned on a full happy path', async () => {
    installFakeWallet()
    vi.spyOn(authApi, 'getWalletNonce').mockResolvedValue('Sign in to TrustMesh\n\nAddress: ...\nNonce: abc')
    const onSigned = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()

    render(<WalletConnectButton label="Connect wallet" onSigned={onSigned} />)
    await user.click(screen.getByRole('button', { name: 'Connect wallet' }))

    await waitFor(() => expect(onSigned).toHaveBeenCalledWith(ADDRESS, '0xdeadbeef'))
  })

  it('shows a clear message when no wallet extension is installed', async () => {
    // window.ethereum intentionally left unset
    const onSigned = vi.fn()
    const user = userEvent.setup()

    render(<WalletConnectButton label="Connect wallet" onSigned={onSigned} />)
    await user.click(screen.getByRole('button', { name: 'Connect wallet' }))

    expect(await screen.findByText(/No wallet extension found/)).toBeInTheDocument()
    expect(onSigned).not.toHaveBeenCalled()
  })

  it('surfaces a rejected signature instead of calling onSigned', async () => {
    installFakeWallet({
      personal_sign: () => {
        throw new Error('User rejected the request.')
      },
    })
    vi.spyOn(authApi, 'getWalletNonce').mockResolvedValue('Sign in to TrustMesh\n\nAddress: ...\nNonce: abc')
    const onSigned = vi.fn()
    const user = userEvent.setup()

    render(<WalletConnectButton label="Connect wallet" onSigned={onSigned} />)
    await user.click(screen.getByRole('button', { name: 'Connect wallet' }))

    expect(await screen.findByText('User rejected the request.')).toBeInTheDocument()
    expect(onSigned).not.toHaveBeenCalled()
  })
})
