import { requireAuth } from '@/lib/auth-utils'
import { cookies } from 'next/headers'
import Header from '@/components/layout/Header'
import { Card, CardContent } from '@/components/ui/card'
import RecordingsTable from '@/components/RecordingsTable'

/**
 * PERUBAHAN:
 * Sebelum: import { prisma } from '@/lib/prisma'
 *          const recordings = await prisma.recording.findMany(...)
 *
 * Sesudah: fetch ke FastAPI /api/recordings dengan JWT token dari cookie
 *          Tidak ada lagi akses Prisma dari Next.js
 */
async function getRecordings(token: string) {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const res = await fetch(`${apiUrl}/api/recordings?limit=50`, {
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
      <main className="p-0 lg:px-4 mt-4">
        <Card>
          <CardContent className="p-6">
            <RecordingsTable recordings={recordings} />
          </CardContent>
        </Card>
      </main>
    </>
  )
}