import { requireAuth } from '@/lib/auth-utils'
import { cookies } from 'next/headers'
import Header from '@/components/layout/Header'
import RecordingsTable from '@/components/RecordingsTable'

async function getRecordings(token: string) {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const res = await fetch(`${apiUrl}/api/recordings?limit=100`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    if (!res.ok) return []
    const data = await res.json()
    return data.data || []
  } catch {
    return []
  }
}

export default async function RecordingsPage() {
  await requireAuth()
  const cookieStore = await cookies()
  const token = cookieStore.get('access_token')?.value || ''
  const recordings = await getRecordings(token)

  return (
    <>
      <Header title="Recordings" subtitle="Manage AUV Video Recordings" emoji="📹" />
      <main className="px-6 py-4">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <RecordingsTable recordings={recordings} />
        </div>
      </main>
    </>
  )
}