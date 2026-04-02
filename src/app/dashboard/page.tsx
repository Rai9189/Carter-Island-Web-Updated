import { requireAuth } from '@/lib/auth-utils'
import Header from '@/components/layout/Header'
import DashboardContent from '@/components/dashboard/DashboardContent'

export default async function DashboardPage() {
  const session = await requireAuth()

  return (
    <>
      <Header title="Dashboard" subtitle={`Welcome back, ${session.user.fullName}`} />
      <main className="p-0 lg:px-4 mt-4">
        <DashboardContent
          userFullName={session.user.fullName}
          userRole={session.user.role}
        />
      </main>
    </>
  )
}