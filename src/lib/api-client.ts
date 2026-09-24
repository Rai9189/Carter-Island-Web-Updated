/**
 * API Client terpusat untuk komunikasi dengan FastAPI backend.
 * Menggantikan semua fetch langsung ke /api/... di Next.js.
 *
 * Cara pakai:
 *   import { apiClient, authHelper } from '@/lib/api-client'
 *
 *   // GET
 *   const data = await apiClient.get('/api/telemetry/latest')
 *
 *   // POST
 *   const res = await apiClient.post('/api/auth/login', { email, password })
 *
 *   // SWR fetcher
 *   const { data } = useSWR('/api/auv-status/latest', apiClient.swrFetcher)
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ==============================
// Tipe data
// ==============================
export interface AuthUser {
  id: string
  email: string
  fullName: string
  role: 'USER' | 'ADMIN'
  phoneNumber: string
}

export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

// ==============================
// Session storage
// ==============================
// Token JWT hanya disimpan di cookie httpOnly 'access_token' yang di-set
// backend saat login (dikirim otomatis via credentials: 'include').
// localStorage hanya menyimpan data profil user untuk kebutuhan UI.
const LEGACY_TOKEN_KEY = 'carter_access_token'
const USER_KEY = 'carter_user'

export const tokenStorage = {
  clear: (): void => {
    if (typeof window === 'undefined') return
    localStorage.removeItem(LEGACY_TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
}

export const userStorage = {
  get: (): AuthUser | null => {
    if (typeof window === 'undefined') return null
    try {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  },
  set: (user: AuthUser): void => {
    if (typeof window === 'undefined') return
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
}

// ==============================
// Core fetch wrapper
// ==============================
async function fetchWithAuth(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  // Token expired atau tidak valid — hapus sesi lalu redirect ke login.
  // Endpoint login/logout dikecualikan: 401 di login = password salah.
  if (response.status === 401 && !endpoint.startsWith('/api/auth/log')) {
    await endSessionAndRedirect()
  }

  return response
}

let isEndingSession = false

async function endSessionAndRedirect(): Promise<void> {
  if (typeof window === 'undefined' || isEndingSession) return
  isEndingSession = true
  tokenStorage.clear()
  try {
    // Hapus cookie di backend — kalau tidak, middleware masih melihat cookie
    // dan me-redirect /auth/login kembali ke /dashboard (redirect loop)
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    })
  } catch {
    // Backend tidak terjangkau — tetap redirect
  }
  window.location.href = '/auth/login'
}

// ==============================
// Error dengan status HTTP — agar pemanggil bisa membedakan 404 (data memang
// kosong) dari error sungguhan (500, backend mati, dst)
// ==============================
export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

export const isApiStatus = (err: unknown, status: number): boolean =>
  err instanceof ApiError && err.status === status

async function throwApiError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({ error: res.statusText }))
  throw new ApiError(err.error || err.detail || `Request gagal: ${res.status}`, res.status)
}

// ==============================
// API Client methods
// ==============================
export const apiClient = {
  get: async <T>(endpoint: string): Promise<T> => {
    const res = await fetchWithAuth(endpoint)
    if (!res.ok) await throwApiError(res)
    return res.json()
  },

  post: async <T>(endpoint: string, body?: unknown): Promise<T> => {
    const res = await fetchWithAuth(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) await throwApiError(res)
    return res.json()
  },

  put: async <T>(endpoint: string, body?: unknown): Promise<T> => {
    const res = await fetchWithAuth(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) await throwApiError(res)
    return res.json()
  },

  patch: async <T>(endpoint: string, body?: unknown): Promise<T> => {
    const res = await fetchWithAuth(endpoint, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) await throwApiError(res)
    return res.json()
  },

  delete: async <T>(endpoint: string): Promise<T> => {
    const res = await fetchWithAuth(endpoint, { method: 'DELETE' })
    if (!res.ok) await throwApiError(res)
    return res.json()
  },

  /**
   * SWR fetcher — pakai ini sebagai pengganti fetcher biasa.
   *
   * Contoh:
   *   const { data } = useSWR('/api/telemetry/latest', apiClient.swrFetcher)
   */
  swrFetcher: async <T>(endpoint: string): Promise<T> => {
    return apiClient.get<T>(endpoint)
  },
}

// ==============================
// Auth helpers
// ==============================
export const authHelper = {
  /**
   * Login — simpan token dan data user.
   * Menggantikan: signIn('credentials', { email, password })
   */
  login: async (email: string, password: string): Promise<AuthUser> => {
    const res = await apiClient.post<{
      success: boolean
      access_token: string
      user: AuthUser
    }>('/api/auth/login', { email, password })

    if (!res.access_token || !res.user) {
      throw new Error('Response login tidak valid dari server')
    }

    userStorage.set(res.user)
    return res.user
  },

  /**
   * Logout — hapus token dan redirect ke login.
   * Menggantikan: signOut()
   */
  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/api/auth/logout')
    } catch {
      // Tetap hapus token lokal meskipun request gagal
    } finally {
      tokenStorage.clear()
      if (typeof window !== 'undefined') {
        window.location.href = '/auth/login'
      }
    }
  },

  /**
   * Dapatkan user yang sedang login dari localStorage.
   * Menggantikan: getServerSession(authOptions)
   */
  getUser: (): AuthUser | null => userStorage.get(),

  /**
   * Cek apakah user sudah login.
   */
  isLoggedIn: (): boolean => !!userStorage.get(),

  /**
   * Cek apakah user adalah admin.
   */
  isAdmin: (): boolean => userStorage.get()?.role === 'ADMIN',

  /**
   * Verifikasi token ke server dan refresh data user.
   * Panggil ini saat pertama load app untuk validasi sesi.
   */
  verifySession: async (): Promise<AuthUser | null> => {
    try {
      const res = await apiClient.get<{ success: boolean; user: AuthUser }>(
        '/api/auth/me'
      )
      if (res.success && res.user) {
        userStorage.set(res.user)
        return res.user
      }
      return null
    } catch {
      tokenStorage.clear()
      return null
    }
  },
}