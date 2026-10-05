import axios, { AxiosError } from 'axios'
import type { ApiErrorBody, TokenPair } from './types'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const API_PREFIX = '/api/v1'

const TOKEN_STORAGE_KEY = 'qfg_tokens'

export interface StoredTokens {
  access_token: string
  refresh_token: string
}

export function getStoredTokens(): StoredTokens | null {
  const raw = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredTokens
  } catch {
    return null
  }
}

export function setStoredTokens(tokens: TokenPair | null) {
  if (tokens) {
    localStorage.setItem(
      TOKEN_STORAGE_KEY,
      JSON.stringify({ access_token: tokens.access_token, refresh_token: tokens.refresh_token }),
    )
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  }
}

/**
 * Normalized error class every caller can rely on. Distinguishes network
 * failures (no response at all — backend unreachable) from real HTTP
 * error statuses, and carries the backend's own `detail` message through
 * rather than a generic "request failed" — the backend's honest
 * unavailable-state messages (501 "model not trained", 503 "graph not
 * configured", etc.) are meant to be shown to the user, not swallowed.
 */
export class ApiError extends Error {
  status: number | null
  detail: string
  isNetworkError: boolean

  constructor(status: number | null, detail: string, isNetworkError = false) {
    super(detail)
    this.status = status
    this.detail = detail
    this.isNetworkError = isNetworkError
  }
}

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 20000,
})

apiClient.interceptors.request.use((config) => {
  const tokens = getStoredTokens()
  if (tokens?.access_token) {
    config.headers.Authorization = `Bearer ${tokens.access_token}`
  }
  return config
})

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const tokens = getStoredTokens()
  if (!tokens?.refresh_token) throw new ApiError(401, 'No refresh token available.')

  const response = await axios.post<TokenPair>(`${API_BASE_URL}${API_PREFIX}/auth/refresh`, {
    refresh_token: tokens.refresh_token,
  })
  setStoredTokens(response.data)
  return response.data.access_token
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config

    if (!error.response) {
      // No response at all: backend unreachable, CORS failure, or timeout.
      return Promise.reject(
        new ApiError(
          null,
          `Cannot reach the backend at ${API_BASE_URL}. Is it running?`,
          true,
        ),
      )
    }

    const status = error.response.status

    // Attempt one silent refresh-and-retry on 401, except for the
    // refresh/login endpoints themselves (avoid infinite loops).
    const url = original?.url || ''
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh') || url.includes('/auth/register')

    if (status === 401 && !isAuthEndpoint && original && !(original as { _retried?: boolean })._retried) {
      try {
        refreshPromise = refreshPromise || refreshAccessToken()
        const newToken = await refreshPromise
        refreshPromise = null
        ;(original as { _retried?: boolean })._retried = true
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${newToken}`
        return apiClient.request(original)
      } catch {
        refreshPromise = null
        setStoredTokens(null)
        window.dispatchEvent(new CustomEvent('qfg:session-expired'))
        return Promise.reject(new ApiError(401, 'Session expired. Please sign in again.'))
      }
    }

    const detail = error.response.data?.detail || error.message || 'Request failed.'
    return Promise.reject(new ApiError(status, detail))
  },
)
