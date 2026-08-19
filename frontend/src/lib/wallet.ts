// Talks to whatever EIP-1193 provider the browser injects (MetaMask or
// compatible) directly — no ethers/web3 dependency for two RPC calls.
// Every wallet extension that matters implements this same interface.

interface Eip1193Provider {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>
}

declare global {
  interface Window {
    ethereum?: Eip1193Provider
  }
}

export class WalletUnavailableError extends Error {
  constructor() {
    super('No wallet extension found. Install MetaMask (or a compatible wallet) and reload the page.')
    this.name = 'WalletUnavailableError'
  }
}

export function hasWallet(): boolean {
  return typeof window !== 'undefined' && window.ethereum !== undefined
}

/** Prompts the wallet's connect UI and returns the address the user picked. */
export async function connectWallet(): Promise<string> {
  if (!window.ethereum) throw new WalletUnavailableError()
  const accounts = (await window.ethereum.request({ method: 'eth_requestAccounts' })) as string[]
  const address = accounts[0]
  if (!address) throw new Error('No account was authorized in the wallet.')
  return address
}

/** Signs `message` (exactly as received from POST /auth/wallet/nonce) with
 * the given address via personal_sign — the standard "sign in" primitive
 * every wallet supports, distinct from a transaction signature (no gas,
 * nothing is broadcast to any chain). */
export async function signMessage(address: string, message: string): Promise<string> {
  if (!window.ethereum) throw new WalletUnavailableError()
  return (await window.ethereum.request({ method: 'personal_sign', params: [message, address] })) as string
}
