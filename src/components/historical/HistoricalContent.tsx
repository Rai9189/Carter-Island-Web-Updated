'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts'
import {
  Fish, Clock, MapPin, TrendingUp,
  Download, Calendar, CheckCircle, XCircle, Activity
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'

const fetcher = apiClient.swrFetcher

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#FF6B9D']

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  Completed: { label: 'Selesai',  color: 'bg-green-100 text-green-700',  icon: CheckCircle },
  Running:   { label: 'Berjalan', color: 'bg-blue-100 text-blue-700',    icon: Activity },
  Aborted:   { label: 'Dibatalkan', color: 'bg-red-100 text-red-700',   icon: XCircle },
}

function formatDuration(startTime: string, endTime: string | null): string {
  if (!endTime) return 'Berlangsung...'
  const diff = new Date(endTime).getTime() - new Date(startTime).getTime()
  const hours   = Math.floor(diff / 3600000)
  const minutes = Math.floor((diff % 3600000) / 60000)
  return `${hours}j ${minutes}m`
}

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(dateStr))
}

export default function HistoricalContent() {
  const [selectedSession, setSelectedSession] = useState<string | null>(null)
  const [statusFilter, setStatusFilter]       = useState<string>('')

  // ── Data fetching ──
  const sessionsUrl = `/api/sessions?limit=50${statusFilter ? `&status_filter=${statusFilter}` : ''}`
  const { data: sessionsData, isLoading: sessionsLoading } = useSWR(sessionsUrl, fetcher)

  const { data: summaryData } = useSWR('/api/fish-counts/summary?limit=10', fetcher)

  const { data: sessionDetailData } = useSWR(
    selectedSession ? `/api/sessions/${selectedSession}` : null,
    fetcher
  )

  const { data: fishCountData } = useSWR(
    selectedSession ? `/api/fish-counts/session/${selectedSession}` : null,
    fetcher
  )

  const sessions: any[]    = (sessionsData as any)?.data || []
  const summary            = (summaryData as any)?.data
  const sessionDetail      = (sessionDetailData as any)?.data
  const fishCounts         = (fishCountData as any)?.data

  // ── Export CSV ──
  const handleExportCSV = () => {
    if (!sessions.length) return

    const headers = ['ID', 'Lokasi', 'Status', 'Mulai', 'Selesai', 'Durasi']
    const rows = sessions.map(s => [
      s.id,
      s.locationName,
      s.status,
      formatDate(s.startTime),
      s.endTime ? formatDate(s.endTime) : '-',
      formatDuration(s.startTime, s.endTime),
    ])

    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url  = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href     = url
    link.download = `riwayat-misi-${new Date().toISOString().split('T')[0]}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleExportSessionCSV = () => {
    if (!fishCounts?.counts?.length || !sessionDetail) return

    const headers = ['Spesies', 'Total Individu', 'Sesi', 'Lokasi']
    const rows = fishCounts.counts.map((c: any) => [
      c.speciesName,
      c.totalCount,
      sessionDetail.id,
      sessionDetail.locationName,
    ])

    const csv  = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url  = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href     = url
    link.download = `deteksi-${sessionDetail.locationName}-${new Date().toISOString().split('T')[0]}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 pb-8">

      {/* ── Summary Cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Misi</p>
              <p className="text-2xl font-bold text-blue-600">{sessions.length}</p>
            </div>
            <Calendar className="h-9 w-9 text-blue-300" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Misi Selesai</p>
              <p className="text-2xl font-bold text-green-600">
                {sessions.filter(s => s.status === 'Completed').length}
              </p>
            </div>
            <CheckCircle className="h-9 w-9 text-green-300" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Spesies</p>
              <p className="text-2xl font-bold text-teal-600">
                {summary?.species?.length ?? 0}
              </p>
            </div>
            <Fish className="h-9 w-9 text-teal-300" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Ikan</p>
              <p className="text-2xl font-bold text-orange-600">
                {summary?.grandTotal ?? 0}
              </p>
            </div>
            <TrendingUp className="h-9 w-9 text-orange-300" />
          </div>
        </CardContent></Card>
      </div>

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Kiri: Tabel Riwayat Misi */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="h-5 w-5 text-blue-500" />
                  Riwayat Misi
                </CardTitle>
                <div className="flex items-center gap-2">
                  {/* Filter status */}
                  <select
                    value={statusFilter}
                    onChange={e => setStatusFilter(e.target.value)}
                    className="border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-600 bg-white"
                  >
                    <option value="">Semua Status</option>
                    <option value="Running">Berjalan</option>
                    <option value="Completed">Selesai</option>
                    <option value="Aborted">Dibatalkan</option>
                  </select>
                  {/* Export CSV */}
                  <button
                    onClick={handleExportCSV}
                    disabled={!sessions.length}
                    className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-lg text-xs font-medium transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export CSV
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {sessionsLoading ? (
                <div className="text-center py-12 text-gray-400 text-sm">Memuat data...</div>
              ) : sessions.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm">Belum ada riwayat misi</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full">
                    <thead className="bg-gray-50 border-y border-gray-100">
                      <tr>
                        {['Lokasi', 'Status', 'Mulai', 'Durasi', 'Detail'].map(h => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {sessions.map((session: any) => {
                        const cfg = STATUS_CONFIG[session.status] || STATUS_CONFIG.Aborted
                        const isSelected = selectedSession === session.id
                        return (
                          <tr
                            key={session.id}
                            className={`hover:bg-gray-50 cursor-pointer transition-colors ${isSelected ? 'bg-blue-50' : ''}`}
                            onClick={() => setSelectedSession(
                              isSelected ? null : session.id
                            )}
                          >
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <MapPin className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                                <span className="text-sm font-medium text-gray-800">
                                  {session.locationName}
                                </span>
                              </div>
                              <p className="text-xs text-gray-400 ml-5 font-mono">
                                {session.id.substring(0, 12)}...
                              </p>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
                                <cfg.icon className="h-3 w-3" />
                                {cfg.label}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-500">
                              {formatDate(session.startTime)}
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-500">
                              {formatDuration(session.startTime, session.endTime)}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`text-xs font-medium ${isSelected ? 'text-blue-600' : 'text-gray-400'}`}>
                                {isSelected ? 'Tutup ↑' : 'Lihat →'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Detail Sesi yang Dipilih */}
          {selectedSession && sessionDetail && (
            <Card className="border-blue-200">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base text-blue-700">
                    Detail: {sessionDetail.locationName}
                  </CardTitle>
                  <button
                    onClick={handleExportSessionCSV}
                    disabled={!fishCounts?.counts?.length}
                    className="flex items-center gap-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white rounded-lg text-xs font-medium"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export Deteksi
                  </button>
                </div>
              </CardHeader>
              <CardContent>
                {/* Ringkasan sesi */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {[
                    { label: 'Deteksi', value: sessionDetail.summary?.detectionCount ?? 0, color: 'text-blue-600' },
                    { label: 'Telemetri', value: sessionDetail.summary?.telemetryCount ?? 0, color: 'text-teal-600' },
                    { label: 'Recording', value: sessionDetail.summary?.recordingCount ?? 0, color: 'text-purple-600' },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="text-center p-3 bg-gray-50 rounded-xl">
                      <p className={`text-2xl font-bold ${color}`}>{value}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                    </div>
                  ))}
                </div>

                {/* Spesies yang terdeteksi */}
                {fishCounts?.counts?.length > 0 ? (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
                      Populasi Ikan ({fishCounts.totalFish} individu)
                    </p>
                    <div className="space-y-2">
                      {fishCounts.counts.map((c: any, i: number) => (
                        <div key={c.id} className="flex items-center gap-3">
                          <div
                            className="w-3 h-3 rounded-full flex-shrink-0"
                            style={{ backgroundColor: COLORS[i % COLORS.length] }}
                          />
                          <span className="text-sm text-gray-700 flex-1">{c.speciesName}</span>
                          <span className="text-sm font-bold text-gray-900">{c.totalCount}</span>
                          <div className="w-24 bg-gray-100 rounded-full h-1.5">
                            <div
                              className="h-1.5 rounded-full"
                              style={{
                                width: `${(c.totalCount / fishCounts.totalFish) * 100}%`,
                                backgroundColor: COLORS[i % COLORS.length],
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 text-center py-4">
                    Belum ada data deteksi ikan dalam sesi ini
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Kanan: Chart Populasi Global */}
        <div className="space-y-4">

          {/* Pie chart total spesies */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Fish className="h-5 w-5 text-teal-500" />
                Total Populasi
              </CardTitle>
            </CardHeader>
            <CardContent>
              {summary?.species?.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={summary.species}
                        dataKey="total"
                        nameKey="speciesName"
                        cx="50%" cy="50%"
                        outerRadius={80}
                        label={({ speciesName, percentage }) =>
                          `${speciesName} ${percentage}%`
                        }
                      >
                        {summary.species.map((_: any, i: number) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value: any, name: any) => [value, name]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="mt-3 space-y-1.5">
                    {summary.species.map((s: any, i: number) => (
                      <div key={s.speciesName} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                          <span className="text-gray-600">{s.speciesName}</span>
                        </div>
                        <span className="font-semibold text-gray-800">{s.total}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="text-center py-8 text-gray-400 text-sm">
                  Belum ada data deteksi
                </div>
              )}
            </CardContent>
          </Card>

          {/* Bar chart per spesies */}
          {summary?.species?.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Perbandingan Spesies</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={summary.species} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis
                      type="category"
                      dataKey="speciesName"
                      tick={{ fontSize: 11 }}
                      width={80}
                    />
                    <Tooltip />
                    <Bar dataKey="total" name="Total" radius={[0, 4, 4, 0]}>
                      {summary.species.map((_: any, i: number) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}