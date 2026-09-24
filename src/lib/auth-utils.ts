import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

export interface AuthUser {
  id: string
  email: string
  fullName: string
  role: 'USER' | 'ADMIN'
  phoneNumber: string
}

export interface AuthSession {
  user: AuthUser
}

function decodeJWT(token: string): AuthUser | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const decoded = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))
    const data = JSON.parse(decoded)
    if (data.exp && Date.now() / 1000 > data.exp) return null
    return {
      id: data.sub || '',
      email: data.email || '',
      fullName: data.fullName || data.full_name || data.email || '',
      role: data.role || 'USER',
      phoneNumber: data.phoneNumber || data.phone_number || '',
    }
  } catch {
    return null
  }
}

export async function getAuthSession(): Promise<AuthSession | null> {
  try {
    const cookieStore = await cookies()
    const token = cookieStore.get('access_token')?.value
    if (!token) return null
    const user = decodeJWT(token)
    if (!user) return null
    return { user }
  } catch {
    return null
  }
}

export async function requireAuth(): Promise<AuthSession> {
  const session = await getAuthSession()
  if (!session) redirect('/auth/login')
  return session
}

export async function requireAdmin(): Promise<AuthSession> {
  const session = await requireAuth()
  if (session.user.role !== 'ADMIN') redirect('/dashboard')
  return session
}

export function hasRole(session: AuthSession | null, role: 'USER' | 'ADMIN'): boolean {
  return session?.user?.role === role
}