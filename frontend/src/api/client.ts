import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

const ACCESS_TOKEN_KEY = 'ondc_access_token'
const REFRESH_TOKEN_KEY = 'ondc_refresh_token'

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, access)
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

export const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.getAccess()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Single-flight refresh: if several requests 401 at once, only the first
// triggers a refresh call; the rest wait on the same promise rather than
// each firing their own (which would race to rotate the refresh token and
// invalidate each other, per backend/README.md's rotation design).
let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = tokenStore.getRefresh()
  if (!refreshToken) return null

  if (!refreshPromise) {
    refreshPromise = axios
      .post<{ access_token: string; refresh_token: string }>(`${BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .then((response) => {
        tokenStore.set(response.data.access_token, response.data.refresh_token)
        return response.data.access_token
      })
      .catch(() => {
        tokenStore.clear()
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    // A 401 from any of these means "these credentials didn't work," not
    // "your session expired" — the caller (a login form) handles it
    // directly. Without this, a failed wallet-login attempt (401, no
    // token was ever set) fell through to the expired-session path below:
    // a doomed refresh attempt, then a hard redirect to /login that wiped
    // the on-screen error before the user ever saw it.
    const isAuthEndpoint =
      original?.url?.includes('/auth/login') ||
      original?.url?.includes('/auth/refresh') ||
      original?.url?.includes('/auth/wallet/')

    if (error.response?.status === 401 && original && !original._retried && !isAuthEndpoint) {
      original._retried = true
      const newToken = await refreshAccessToken()
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
      tokenStore.clear()
      window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}
