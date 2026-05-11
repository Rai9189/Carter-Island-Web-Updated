import { requireAuth } from '@/lib/auth-utils'
import Header from '@/components/layout/Header'
import HelpContent from '@/components/help/HelpContent'

export default async function HelpPage() {
  await requireAuth()

  return (
    <>
      <Header
        title="Help"
        subtitle="Help & Documentation"
        emoji="📖"
      />
      <main className="p-0 lg:px-4 mt-4">
        <HelpContent />
      </main>
    </>
  )
}