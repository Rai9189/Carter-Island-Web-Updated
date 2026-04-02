import { requireAuth } from '@/lib/auth-utils'
import Sidebar from '@/components/layout/Sidebar'

/**
 * PERUBAHAN:
 * requireAuth() sekarang baca JWT dari cookie, bukan NextAuth session.
 * Tipe AuthSession kompatibel — session.user.fullName, session.user.role dst tetap sama.
 */
export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await requireAuth()

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar session={session} />
      <div className="dashboard-content">
        <main className="p-0 lg:p-0">
          {children}
        </main>
      </div>
    </div>
  )
}