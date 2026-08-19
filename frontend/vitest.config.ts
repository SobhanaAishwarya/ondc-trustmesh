import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Separate from vite.config.ts (which stays build/dev-server-only) so the
// production build config never has to know about the test runner. Reuses
// only what tests actually need — no tailwindcss plugin, since jsdom tests
// render components without going through the CSS pipeline.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    // e2e/ is Playwright's own suite (test:e2e) — it uses Playwright's
    // `test()` global, which collides with Vitest's if picked up here.
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
