import { requireAuth } from '@/lib/auth-utils'
import Header from '@/components/layout/Header'
import AnalyticsContent from '@/components/analytics/AnalyticsContent'

export default async function AnalyticsPage() {
  await requireAuth()

  return (
    <>
      <Header title="Analytics" subtitle="Fish Detection, Telemetry & AUV Status Analytics" />
      <main className="p-0 lg:px-4 mt-4">
        <AnalyticsContent />
      </main>
    </>
  )
}