/**
 * Auth utility untuk frontend.
 * Menggantikan NextAuth authOptions.
 *
 * Sebelumnya: getServerSession(authOptions) di setiap page/component
 * Sekarang: authHelper.getUser() dari localStorage
 *           authHelper.verifySession() untuk validasi ke server
 */

export { authHelper, tokenStorage, userStorage } from './api-client'
export type { AuthUser } from './api-client'

/**
 * Panduan migrasi dari NextAuth:
 *
 * SEBELUM (NextAuth):
 *   import { getServerSession } from 'next-auth'
 *   import { authOptions } from '@/lib/auth'
 *   const session = await getServerSession(authOptions)
 *   if (!session) redirect('/auth/login')
 *   const user = session.user
 *
 * SESUDAH (JWT):
 *   import { authHelper } from '@/lib/auth'
 *   const user = authHelper.getUser()
 *   if (!user) redirect('/auth/login')
 *
 * UNTUK SERVER COMPONENT (Next.js):
 *   Gunakan middleware atau cookies untuk validasi di server side.
 *   Lihat src/middleware.ts untuk implementasi lengkap.
 */