import { test, expect, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Real signatures throughout, produced by the backend's own eth_account —
// the point of this test is proving the actual signed-challenge flow
// works end to end (browser -> axios -> FastAPI -> eth_account.recover_
// message -> real JWTs), not exercising a mocked stand-in. There's no
// real MetaMask extension to drive here, so `window.ethereum` is a thin
// injected stub — but every value it returns is genuine: a real keypair,
// a real personal_sign-compatible signature over the exact message the
// backend issued.
const PYTHON = path.resolve(__dirname, '../../backend/.venv/Scripts/python.exe')
const BACKEND_DIR = path.resolve(__dirname, '../../backend')

function pythonEval(code: string): string {
  // Windows Python prints CRLF; execFileSync doesn't normalize it, so a
  // bare .trim() still leaves a trailing \r on every line but the last.
  return execFileSync(PYTHON, ['-c', code], { cwd: BACKEND_DIR, encoding: 'utf-8' }).replace(/\r\n/g, '\n').trim()
}

function createTestWallet(): { address: string; privateKey: string } {
  const [address, privateKey] = pythonEval(
    "from eth_account import Account; a = Account.create(); print(a.address); print(a.key.hex())",
  ).split('\n')
  return { address, privateKey }
}

function signWithTestWallet(privateKey: string, message: string): string {
  return pythonEval(
    `
from eth_account import Account
from eth_account.messages import encode_defunct
signed = Account.sign_message(encode_defunct(text=${JSON.stringify(message)}), private_key=${JSON.stringify(privateKey)})
print("0x" + signed.signature.hex())
`.trim(),
  )
}

async function installTestWallet(page: Page, wallet: { address: string; privateKey: string }) {
  await page.exposeFunction('__signWithTestWallet', (message: string) => signWithTestWallet(wallet.privateKey, message))
  await page.addInitScript((address) => {
    ;(window as unknown as { ethereum: unknown }).ethereum = {
      request: async ({ method, params }: { method: string; params?: unknown[] }) => {
        if (method === 'eth_requestAccounts') return [address]
        if (method === 'personal_sign') {
          const message = (params as string[])[0]
          return (window as unknown as { __signWithTestWallet: (m: string) => Promise<string> }).__signWithTestWallet(
            message,
          )
        }
        throw new Error(`unexpected method: ${method}`)
      },
    }
  }, wallet.address)
}

test('buyer links a wallet, logs out, and signs back in with it — no password', async ({ page }) => {
  const stamp = Date.now()
  const wallet = createTestWallet()
  await installTestWallet(page, wallet)

  // --- Sign up normally, then link the wallet from Settings ---
  await page.goto('/signup')
  await page.locator('form input').nth(0).fill('E2E Wallet Buyer')
  await page.locator('input[type="email"]').fill(`e2e_wallet_${stamp}@example.com`)
  await page.locator('input[type="password"]').fill('buyerpass123')
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.waitForURL('**/buyer')

  await page.goto('/buyer/settings')
  await expect(page.getByText('No wallet linked yet.')).toBeVisible()
  await page.getByRole('button', { name: 'Connect & verify wallet' }).click()
  await expect(page.getByText('Verified')).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText(wallet.address)).toBeVisible()

  // --- Log out, then sign back in with only the wallet — no password ---
  await page.getByRole('button', { name: 'Log out' }).click()
  await page.waitForURL('**/login')

  await page.getByRole('button', { name: 'Sign in with wallet' }).click()
  await page.waitForURL('**/buyer', { timeout: 10_000 })
  await page.goto('/buyer/settings')
  await expect(page.getByText('Verified')).toBeVisible()
  await expect(page.getByText(wallet.address)).toBeVisible()
})

test('signing in with a wallet that was never linked is rejected, not silently accepted', async ({ page }) => {
  const wallet = createTestWallet()
  await installTestWallet(page, wallet)

  await page.goto('/login')
  await page.getByRole('button', { name: 'Sign in with wallet' }).click()

  await expect(page.getByText(/log in with a password first/i)).toBeVisible({ timeout: 10_000 })
  await expect(page).toHaveURL(/\/login/)
})
