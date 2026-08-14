import { test, expect } from '@playwright/test'

// Exercises the full stack for real: React form -> axios -> FastAPI ->
// SQLAlchemy -> the fraud-scoring service -> the order response -> React
// Query's cache -> the rendered UI. Needs the backend running against a
// live (disposable) database — see backend/README.md. Not part of the
// backend's own 96-test suite, which needs zero external services; this
// is the one place that genuinely needs both halves running together.
test('seller lists a product, buyer signs up and buys it', async ({ page }) => {
  const stamp = Date.now()
  const consoleErrors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })

  // --- Seller: sign up, add a product ---
  await page.goto('/signup')
  await page.getByRole('button', { name: 'seller' }).click()
  await page.locator('form input').nth(0).fill('E2E Seller')
  await page.locator('input[type="email"]').fill(`e2e_seller_${stamp}@example.com`)
  await page.locator('input[type="password"]').fill('sellerpass123')
  await page.locator('form input').nth(3).fill('E2E Shop')
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.waitForURL('**/seller')

  await page.goto('/seller/products')
  await page.getByRole('button', { name: '+ Add product' }).click()
  await page.getByText('Add a product').waitFor()
  await page.locator('form input').nth(0).fill('E2E Wireless Mouse')
  await page.locator('form select').selectOption('Electronics')
  await page.locator('form textarea').fill('A smooth wireless mouse')
  await page.locator('form input[type="number"]').nth(0).fill('499')
  await page.getByRole('button', { name: 'Create product' }).click()
  await expect(page.getByText('E2E Wireless Mouse')).toBeVisible()

  // --- Buyer: sign up, browse, buy ---
  await page.getByRole('button', { name: 'Log out' }).click()
  await page.waitForURL('**/login')

  await page.goto('/signup')
  await page.locator('form input').nth(0).fill('E2E Buyer')
  await page.locator('input[type="email"]').fill(`e2e_buyer_${stamp}@example.com`)
  await page.locator('input[type="password"]').fill('buyerpass123')
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.waitForURL('**/buyer')

  await page.goto('/buyer/products')
  await expect(page.getByText('E2E Wireless Mouse')).toBeVisible({ timeout: 10_000 })
  await page.getByText('E2E Wireless Mouse').click()
  await expect(page.getByText('Purchase', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Buy now' }).click()
  await page.waitForURL('**/buyer/orders*')
  await expect(page.getByText('E2E Wireless Mouse × 1')).toBeVisible()
  await expect(page.getByText('₹499.00')).toBeVisible()

  expect(consoleErrors, `Unexpected browser console errors: ${consoleErrors.join('\n')}`).toEqual([])
})
