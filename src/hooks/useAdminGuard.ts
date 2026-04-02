'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { authHelper, type AuthUser } from '@/lib/api-client'

interface AdminGuardResult {
  session: { user: AuthUser } | null
  status: 'loading' | 'authenticated' | 'unauthenticated'
}

/**
 * Hook untuk proteksi halaman admin di client component.
 * Menggantikan: useSession() dari NextAuth
 */
export function useAdminGuard(): AdminGuardResult {
  const router = useRouter()
  const [session, setSession] = useState<{ user: AuthUser } | null>(null)
  const [status, setStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading')

  useEffect(() => {
    const check = async () => {
      // Cek localStorage dulu (cepat)
      const user = authHelper.getUser()

      if (!user) {
        setStatus('unauthenticated')
        router.push('/auth/login')
        return
      }

      if (user.role !== 'ADMIN') {
        setStatus('authenticated')
        setSession({ user })
        toast.error('Access denied. Admin privileges required.')
        router.push('/dashboard')
        return
      }

      // Verifikasi ke server (pastikan token masih valid)
      const verified = await authHelper.verifySession()
      if (!verified) {
        setStatus('unauthenticated')
        router.push('/auth/login')
        return
      }

      setSession({ user: verified })
      setStatus('authenticated')
    }

    check()
  }, [router])

  return { session, status }
}