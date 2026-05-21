'use client'

import { useState, useMemo } from 'react'
import useSWR from 'swr'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts'
import { apiClient } from '@/lib/api-client'

const fetcher = apiClient.swrFetcher

const SPECIES_COLORS: Record<string, string> = {
  Kerapu: '#3b82f6',
  Bandeng: '#22c55e',
  Teri: '#f97316',
  Lainnya: '#9ca3af',
  Unknown: '#9ca3af',
}
const DEFAULT_COLORS = ['#3b82f6', '#22c55e', '#f97316', '#9ca3af', '#a855f7', '#ec4899']
function getColor(name: string, idx: number) {
  return SPECIES_COLORS[name] || DEFAULT_COLORS[idx % DEFAULT_COLORS.length]
}

type RangeKey = '7d' | '30d' | '90d' | 'all'
const RANGE_OPTIONS: { label: string; key: RangeKey; hours: number }[] = [
  { label: '7 Hari', key: '7d', hours: 168 },
  { label: '30 Hari', key: '30d', hours: 720 },
  { label: '3 Bulan', key: '90d', hours: 2160 },
  { label: 'Semua', key: 'all', hours: 99999 },
]

function fmtDate(t: string) {
  const d = new Date(t)
  if (isNaN(d.getTime())) return '—'
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
function fmtTimeRange(startTime: string, endTime: string | null): string {
  const start = new Date(startTime).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
  if (!endTime) return start
  const end = new Date(endTime).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
  return `${start}-${end}`
}
function fmtDuration(startTime: string, endTime: string | null): string {
  if (!endTime) return 'Berlangsung...'
  const diff = new Date(endTime).getTime() - new Date(startTime).getTime()
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  return `${h}j ${String(m).padStart(2, '0')}m`
}
function fmtAxisDate(t: string) {
  return new Date(t).toLocaleDateString('id-ID', { month: 'short', day: 'numeric' })
}

function downloadSessionCSV(session: any, fishCounts: any, telemetrySummary: any) {
  const headers = ['TANGGAL', 'NAMA MISI', 'WAKTU MISI', 'SESSION ID', 'DURASI', 'JML IKAN', 'SPESIES', 'PH', 'TDS', 'SUHU', 'DO']
  const row = [
    fmtDate(session.startTime),
    session.locationName,
    fmtTimeRange(session.startTime, session.endTime),
    `session_${session.id.slice(-3)}`,
    fmtDuration(session.startTime, session.endTime),
    fishCounts?.totalFish ?? 0,
    fishCounts?.speciesCount ?? 0,
    telemetrySummary?.avgPh ?? '',
    telemetrySummary?.avgTds ?? '',
    telemetrySummary?.avgTemp ?? '',
    telemetrySummary?.avgDo ?? '',
  ]
  const csv = [headers.join(','), row.join(',')].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `misi-${session.locationName}-${fmtDate(session.startTime)}.csv`; a.click()
  URL.revokeObjectURL(url)
}

// Trend chart wrapper
function TrendChart({ title, data, dataKey, color, range, unit, domain }: {
  title: string; data: any[]; dataKey: string; color: string
  range: string; unit?: string; domain?: [number, number]
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
        <span className="text-xs text-gray-400">{range} terakhir</span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="date" tickFormatter={fmtAxisDate} tick={{ fontSize: 10 }} />
          <YAxis domain={domain} tick={{ fontSize: 10 }} />
          <Tooltip formatter={(v: any) => [`${v}${unit ?? ''}`, title]} labelFormatter={fmtAxisDate} />
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={{ r: 3, fill: color }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function HistoricalContent() {
  const [rangeKey, setRangeKey] = useState<RangeKey>('30d')
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30); return d.toISOString().split('T')[0]
  })
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0])

  const selectedRange = RANGE_OPTIONS.find(r => r.key === rangeKey)!
  const rangeLabel = selectedRange.label

  // Fetch sessions
  const { data: sessionsData } = useSWR('/api/analytics/sessions', fetcher, { refreshInterval: 60000 })
  const allSessions: any[] = (sessionsData as any)?.data || []

  // Filter sessions by date range
  const sessions = useMemo(() => {
    if (rangeKey === 'all') return allSessions
    const from = new Date(dateFrom).getTime()
    const to = new Date(dateTo + 'T23:59:59').getTime()
    return allSessions.filter(s => {
      const t = new Date(s.startTime).getTime()
      return t >= from && t <= to
    })
  }, [allSessions, rangeKey, dateFrom, dateTo])

  // Fetch telemetry analytics
  const { data: telemetryData } = useSWR(
    `/api/analytics/telemetry?hours=${selectedRange.hours}`,
    fetcher, { refreshInterval: 60000 }
  )
  const { data: detectionData } = useSWR(
    `/api/analytics/detections?hours=${selectedRange.hours}`,
    fetcher, { refreshInterval: 60000 }
  )
  const { data: fishSummaryData } = useSWR('/api/fish-counts/summary?limit=10', fetcher)
  const { data: allFishCountsData } = useSWR('/api/fish-counts?limit=500', fetcher)

  const telemetry = (telemetryData as any)?.data
  const detections = (detectionData as any)?.data
  const fishSummary = (fishSummaryData as any)?.data
  const allFishCounts: any[] = (allFishCountsData as any)?.data || []

  // Build session id → date map for joining fish counts
  const sessionDateMap = useMemo(() => {
    const map: Record<string, string> = {}
    allSessions.forEach(s => { map[s.id] = fmtDate(s.startTime) })
    return map
  }, [allSessions])

  // pH trend — from telemetry data
  const phTrend = (telemetry?.ph || []).filter((_: any, i: number) => i % 10 === 0).map((t: any) => ({
    date: t.time, value: t.value
  }))
  const tdsTrend = (telemetry?.tds || []).filter((_: any, i: number) => i % 10 === 0).map((t: any) => ({
    date: t.time, value: t.value
  }))
  const doTrend = (telemetry?.dissolvedOxygen || []).filter((_: any, i: number) => i % 10 === 0).map((t: any) => ({
    date: t.time, value: t.value
  }))
  const tempTrend = (telemetry?.temperature || []).filter((_: any, i: number) => i % 10 === 0).map((t: any) => ({
    date: t.time, value: t.value
  }))

  // Summary stats
  const avgPh = telemetry?.summary?.avgPh ?? 0
  const avgDo = telemetry?.summary?.avgDo ?? 0
  const totalFish = fishSummary?.grandTotal ?? 0
  const totalMisi = sessions.length

  // Comparison to previous period (dummy delta for now)
  const prevSessions = allSessions.length - sessions.length

  // Stacked bar data — fish counts per species grouped by date (filtered by date range)
  const stackedBarData = useMemo(() => {
    const byDate: Record<string, Record<string, number>> = {}

    // Initialize date buckets from filtered sessions
    sessions.forEach(s => {
      const d = fmtDate(s.startTime)
      if (!byDate[d]) byDate[d] = {}
    })

    // Aggregate actual fish counts into date buckets via sessionId → date join
    allFishCounts.forEach((fc: any) => {
      const date = sessionDateMap[fc.sessionId]
      if (!date || !byDate[date]) return
      const sp = fc.speciesName
      byDate[date][sp] = (byDate[date][sp] || 0) + (fc.totalCount || 0)
    })

    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, counts]) => ({ date, ...counts }))
  }, [sessions, allFishCounts, sessionDateMap])

  const speciesKeys = useMemo(() => {
    if (fishSummary?.species?.length > 0) {
      return fishSummary.species.map((s: any) => s.speciesName)
    }
    // Fallback: collect species from actual fish counts in chart data
    const fromData = new Set<string>()
    stackedBarData.forEach(row => {
      Object.keys(row).forEach(k => { if (k !== 'date') fromData.add(k) })
    })
    return fromData.size > 0 ? Array.from(fromData) : ['Kerapu', 'Bandeng', 'Teri', 'Lainnya']
  }, [fishSummary, stackedBarData])

  return (
    <div className="px-6 py-4 space-y-4">

      {/* ── Filter Bar ── */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-3 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Dari:</span>
          <input type="date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setRangeKey('all') }}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-blue-400" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Sampai:</span>
          <input type="date" value={dateTo} onChange={e => { setDateTo(e.target.value); setRangeKey('all') }}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-blue-400" />
        </div>
        <div className="flex items-center gap-1">
          {RANGE_OPTIONS.map(opt => (
            <button key={opt.key} onClick={() => {
              setRangeKey(opt.key)
              if (opt.key !== 'all') {
                const d = new Date()
                setDateTo(d.toISOString().split('T')[0])
                d.setHours(d.getHours() - opt.hours)
                setDateFrom(d.toISOString().split('T')[0])
              }
            }}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${rangeKey === opt.key ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-100'}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <button className="ml-auto px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
          Terapkan Filter
        </button>
      </div>

      {/* ── Summary Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label: 'Total Misi', value: totalMisi,
            delta: prevSessions >= 0 ? `+${sessions.length - Math.max(0, prevSessions)} dari bulan lalu` : null,
            deltaUp: true, color: 'text-gray-800',
          },
          {
            label: 'Total Ikan Terdeteksi', value: totalFish,
            delta: '+128 dari bulan lalu', deltaUp: true, color: 'text-gray-800',
          },
          {
            label: 'Rata-rata pH', value: avgPh > 0 ? avgPh.toFixed(1) : '—',
            delta: avgPh > 0 ? (avgPh < 6.5 ? '-0.2 dari bulan lalu' : null) : null,
            deltaUp: false, color: 'text-gray-800',
          },
          {
            label: 'Rata-rata DO', value: avgDo > 0 ? `${avgDo.toFixed(1)} mg/L` : '—',
            delta: avgDo > 0 && avgDo < 6 ? 'Perlu perhatian' : null,
            deltaUp: false, color: 'text-gray-800',
          },
        ].map(({ label, value, delta, deltaUp, color }) => (
          <div key={label} className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4">
            <p className="text-xs text-gray-400 mb-1">{label}</p>
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
            {delta && (
              <p className={`text-xs mt-1 flex items-center gap-0.5 ${deltaUp ? 'text-green-500' : 'text-red-500'}`}>
                {deltaUp ? '▲' : '▼'} {delta}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* ── 4 Trend Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TrendChart title="Tren pH Air" data={phTrend} dataKey="value" color="#3b82f6" range={rangeLabel} domain={[2, 14]} />
        <TrendChart title="Tren DO (Dissolved Oxygen)" data={doTrend} dataKey="value" color="#22c55e" range={rangeLabel} unit=" mg/L" />
        <TrendChart title="Tren TDS" data={tdsTrend} dataKey="value" color="#f97316" range={rangeLabel} unit=" ppm" />
        <TrendChart title="Tren Suhu Air" data={tempTrend} dataKey="value" color="#ef4444" range={rangeLabel} unit="°C" />
      </div>

      {/* ── Stacked Bar: Tren Deteksi Ikan per Misi ── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-700">Tren Deteksi Ikan per Misi</h3>
          <span className="text-xs text-gray-400">Akumulasi per survei</span>
        </div>
        {stackedBarData.length > 0 && stackedBarData.some(row => speciesKeys.some((sp: string) => row[sp] > 0)) ? (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={stackedBarData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="date" tickFormatter={fmtAxisDate} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend iconType="circle" iconSize={10} />
              {speciesKeys.map((sp: string, i: number) => (
                <Bar key={sp} dataKey={sp} stackId="a" fill={getColor(sp, i)} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-40 text-gray-300 text-sm">Belum ada data deteksi per misi</div>
        )}
      </div>

      {/* ── Riwayat Misi Table ── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700">Riwayat Misi</h3>
          <span className="text-xs text-gray-400">{sessions.length} misi tercatat</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                {['TANGGAL', 'NAMA MISI', 'WAKTU MISI', 'SESSION ID', 'DURASI', 'JML IKAN', 'SPESIES', 'PH', 'TDS', 'SUHU', 'DO', 'AKSI'].map(h => (
                  <th key={h} className="px-4 py-3 text-left font-semibold text-gray-400 tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sessions.length > 0 ? sessions.slice(0, 20).map((s: any) => (
                <SessionRow key={s.id} session={s} />
              )) : (
                <tr><td colSpan={12} className="px-4 py-10 text-center text-gray-300">Belum ada data misi</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── Session Row — fetch fish + telemetry per session ────────────────────────
function SessionRow({ session }: { session: any }) {
  const { data: fishData } = useSWR(`/api/fish-counts/session/${session.id}`, apiClient.swrFetcher, { revalidateOnFocus: false })
  const { data: telData } = useSWR(`/api/analytics/telemetry?hours=9999&session_id=${session.id}`, apiClient.swrFetcher, { revalidateOnFocus: false })

  const fish = (fishData as any)?.data
  const tel = (telData as any)?.data?.summary

  const sessionLabel = `session_${session.id.slice(-3)}`

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmtDate(session.startTime)}</td>
      <td className="px-4 py-3 font-semibold text-gray-800 whitespace-nowrap">{session.locationName}</td>
      <td className="px-4 py-3 text-gray-500 font-mono whitespace-nowrap">{fmtTimeRange(session.startTime, session.endTime)}</td>
      <td className="px-4 py-3">
        <span className="font-mono text-gray-400 border border-gray-200 px-2 py-0.5 rounded-lg bg-gray-50">{sessionLabel}</span>
      </td>
      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmtDuration(session.startTime, session.endTime)}</td>
      <td className="px-4 py-3 font-bold text-blue-600">{fish?.totalFish ?? '—'}</td>
      <td className="px-4 py-3 font-bold text-green-600">{fish?.speciesCount ?? '—'}</td>
      <td className="px-4 py-3 text-gray-600">{tel?.avgPh ?? '—'}</td>
      <td className="px-4 py-3 text-yellow-600">{tel?.avgTds ?? '—'}</td>
      <td className="px-4 py-3 text-gray-600">{tel?.avgTemp ?? '—'}</td>
      <td className="px-4 py-3 text-orange-500">{tel?.avgDo ?? '—'}</td>
      <td className="px-4 py-3">
        <button
          onClick={() => downloadSessionCSV(session, fish, tel)}
          className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-white text-xs font-medium rounded-lg transition-colors whitespace-nowrap"
        >
          ↓ CSV
        </button>
      </td>
    </tr>
  )
}