'use client'

import { useState, useMemo } from 'react'
import useSWR from 'swr'
import { toast } from 'sonner'
import {
  LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
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

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return `${h}j ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}d`
}

function fmtTime(t: string) {
  return new Date(t).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
}

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

function getPhColor(ph: number) {
  if (ph < 6.5) return 'text-red-500'
  if (ph > 8.5) return 'text-yellow-500'
  return 'text-gray-800'
}
function getTdsColor(tds: number) {
  if (tds > 300) return 'text-yellow-500'
  return 'text-gray-800'
}
function getDoColor(do_: number) {
  if (do_ < 6.0) return 'text-red-500'
  return 'text-gray-800'
}
function getTempColor(temp: number) {
  if (temp < 26 || temp > 30) return 'text-yellow-500'
  return 'text-gray-800'
}

function StatusBadge({ value, type }: { value: number; type: 'ph' | 'tds' | 'do' | 'temp' }) {
  const configs = {
    ph: { normal: [6.5, 8.5], label: (v: number) => v < 6.5 ? 'Di Bawah Normal' : v > 8.5 ? 'Di Atas Normal' : 'Normal' },
    tds: { normal: [0, 300], label: (v: number) => v > 300 ? 'Di Atas Normal' : 'Normal' },
    do: { normal: [6, 8], label: (v: number) => v < 6 ? 'Di Bawah Normal' : v > 8 ? 'Di Atas Normal' : 'Normal' },
    temp: { normal: [26, 30], label: (v: number) => v < 26 || v > 30 ? 'Di Atas Normal' : 'Normal' },
  }
  const cfg = configs[type]
  const label = cfg.label(value)
  const isNormal = label === 'Normal'
  const isBelow = label === 'Di Bawah Normal'
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${isNormal ? 'bg-green-100 text-green-700' : isBelow ? 'bg-red-100 text-red-600' : 'bg-yellow-100 text-yellow-700'}`}>
      {!isNormal && <span className="mr-0.5">{isBelow ? '▼' : '▲'}</span>}{label}
    </span>
  )
}

function csvCell(v: unknown): string {
  const s = v === null || v === undefined ? '' : String(v)
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function downloadCSV(data: any[], filename: string, headers: string[], rowFn: (row: any) => unknown[]) {
  const rows = [headers.map(csvCell).join(','), ...data.map(r => rowFn(r).map(csvCell).join(','))]
  // BOM agar Excel membaca file sebagai UTF-8
  const blob = new Blob(['﻿' + rows.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

// Ambil semua baris sesi untuk export — tabel di layar hanya memuat 20 baris terbaru
async function fetchAllRows(endpoint: string, total: number): Promise<any[]> {
  const res = await apiClient.get<any>(`${endpoint}&limit=${Math.max(total, 1)}`)
  return res?.data || []
}

export default function AnalyticsContent() {
  const [dateFilter, setDateFilter] = useState(() => new Date().toISOString().split('T')[0])
  const [selectedSessionId, setSelectedSessionId] = useState('')

  // Fetch semua sessions, filter by date di client
  const { data: sessionsData } = useSWR('/api/analytics/sessions', fetcher, { refreshInterval: 30000 })
  const allSessions: any[] = (sessionsData as any)?.data || []

  // Filter sessions by date (toleransi ±1 hari untuk timezone)
  const sessions: any[] = allSessions.filter((s: any) => {
    if (!dateFilter) return true
    const sessionDate = new Date(s.startTime).toLocaleDateString('sv-SE') // YYYY-MM-DD
    return sessionDate === dateFilter
  })

  // Auto-select: prioritas sessions (filtered by date), fallback ke session terbaru
  const availableSessions = sessions.length > 0 ? sessions : allSessions.slice(0, 1)
  const sessionId = selectedSessionId || availableSessions[0]?.id || ''
  const activeSession = availableSessions.find((s: any) => s.id === sessionId) || availableSessions[0]

  // Fetch analytics
  const { data: detectionData, isLoading: detectionLoading } = useSWR(
    sessionId ? `/api/analytics/detections?hours=9999&session_id=${sessionId}` : null,
    fetcher, { refreshInterval: 30000 }
  )
  const { data: telemetryData, isLoading: telemetryLoading } = useSWR(
    sessionId ? `/api/analytics/telemetry?hours=9999&session_id=${sessionId}` : null,
    fetcher, { refreshInterval: 30000 }
  )
  const { data: detectionListData } = useSWR(
    sessionId ? `/api/detections?session_id=${sessionId}&limit=20` : null,
    fetcher, { refreshInterval: 30000 }
  )
  const { data: telemetryListData } = useSWR(
    sessionId ? `/api/telemetry?session_id=${sessionId}&limit=20` : null,
    fetcher, { refreshInterval: 30000 }
  )

  const isAnalyticsLoading = sessionId ? (detectionLoading || telemetryLoading) : false

  const detections = (detectionData as any)?.data
  const telemetry = (telemetryData as any)?.data
  const detectionList: any[] = (detectionListData as any)?.data || []
  const telemetryList: any[] = (telemetryListData as any)?.data || []
  const detectionTotal: number = (detectionListData as any)?.pagination?.total ?? detectionList.length
  const telemetryTotal: number = (telemetryListData as any)?.pagination?.total ?? telemetryList.length

  const totalDetections = detections?.summary?.totalDetections ?? 0
  const uniqueSpecies = detections?.summary?.uniqueSpecies ?? 0
  const avgConfidence = detections?.summary?.avgConfidence ?? 0
  const speciesDist: any[] = detections?.speciesDistribution || []
  const speciesTotal = speciesDist.reduce((s: number, c: any) => s + c.count, 0)
  const timeSeries: any[] = detections?.timeSeries || []

  const avgPh = telemetry?.summary?.avgPh ?? 0
  const avgTds = telemetry?.summary?.avgTds ?? 0
  const avgDo = telemetry?.summary?.avgDo ?? 0
  const avgTemp = telemetry?.summary?.avgTemp ?? 0

  // Session duration in seconds
  const sessionDuration = activeSession?.endTime && activeSession?.startTime
    ? Math.floor((new Date(activeSession.endTime).getTime() - new Date(activeSession.startTime).getTime()) / 1000)
    : 0

  const missionName = activeSession?.locationName ?? '—'
  const sessionLabel = `session_${(sessionId || '').slice(-3)}`

  return (
    <div className="px-6 py-4 space-y-4">

      {/* ── Filter: Tanggal + Misi ── */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Tanggal:</span>
            <input
              type="date"
              value={dateFilter}
              onChange={e => { setDateFilter(e.target.value); setSelectedSessionId('') }}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-blue-400"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Misi:</span>
            <select
              value={sessionId}
              onChange={e => setSelectedSessionId(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-blue-400"
            >
              {availableSessions.length === 0 && <option value="">Tidak ada misi</option>}
              {availableSessions.map((s: any) => (
                <option key={s.id} value={s.id}>{s.locationName}</option>
              ))}
            </select>
          </div>
        </div>
        {sessionId && (
          <span className="text-xs font-mono text-gray-400 border border-gray-200 px-3 py-1.5 rounded-lg bg-gray-50">
            id_session: {sessionLabel}
          </span>
        )}
      </div>

      {!sessionId ? (
        <div className="flex flex-col items-center justify-center h-60 text-gray-300">
          <div className="w-16 h-16 rounded-full border-4 border-dashed border-gray-200 flex items-center justify-center mb-3">
            <span className="text-2xl">📊</span>
          </div>
          <p className="text-sm text-gray-400">Pilih tanggal dan misi untuk melihat analytics</p>
        </div>
      ) : (
        <>
          {/* Loading indicator saat ganti sesi */}
          {isAnalyticsLoading && (
            <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-500">
              <div className="w-3 h-3 border-2 border-blue-300 border-t-blue-500 rounded-full animate-spin" />
              Memuat data analytics...
            </div>
          )}

          {/* ── Row 1: Summary Cards ── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              {
                label: 'Total Deteksi Ikan',
                value: totalDetections,
                sub: 'Sesi ini',
                icon: '🐟',
                iconBg: 'bg-blue-50',
              },
              {
                label: 'Total Spesies',
                value: uniqueSpecies,
                sub: speciesDist.map((s: any) => s.species).join(', ') || '—',
                icon: '📊',
                iconBg: 'bg-green-50',
              },
              {
                label: 'Durasi Misi',
                value: sessionDuration > 0 ? formatDuration(sessionDuration) : '—',
                sub: 'Total waktu misi berlangsung',
                icon: '⏱',
                iconBg: 'bg-yellow-50',
              },
              {
                label: 'Avg Confidence AI',
                value: avgConfidence > 0 ? `${(avgConfidence * 100).toFixed(0)}%` : '—',
                sub: 'AI detection',
                icon: '🎯',
                iconBg: 'bg-purple-50',
              },
            ].map(({ label, value, sub, icon, iconBg }) => (
              <div key={label} className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4 flex items-start justify-between">
                <div>
                  <p className="text-xs text-gray-400 mb-1">{label}</p>
                  <p className="text-2xl font-bold text-gray-800 leading-tight">{value}</p>
                  <p className="text-xs text-gray-400 mt-1 truncate max-w-[160px]">{sub}</p>
                </div>
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg ${iconBg}`}>
                  {icon}
                </div>
              </div>
            ))}
          </div>

          {/* ── Row 2: Species count per spesies ── */}
          {speciesDist.length > 0 && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {speciesDist.slice(0, 4).map((s: any, i: number) => {
                const pct = speciesTotal > 0 ? ((s.count / speciesTotal) * 100).toFixed(1) : '0'
                const color = getColor(s.species, i)
                return (
                  <div key={s.species} className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4">
                    <p className="text-3xl font-bold mb-1" style={{ color }}>{s.count}</p>
                    <p className="text-sm text-gray-600 font-medium">{s.species}</p>
                    <p className="text-xs mt-1 mb-2" style={{ color }}>{pct}%</p>
                    <div className="h-1 rounded-full bg-gray-100 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* ── Row 3: Line chart + Donut ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            {/* Fish Detections Over Time */}
            <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-700">Fish Detections Over Time</h3>
                <span className="text-xs text-gray-400 border border-gray-200 px-2 py-0.5 rounded-lg">24h</span>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={timeSeries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip labelFormatter={t => fmtTime(String(t))} />
                  <Line type="monotone" dataKey="detections" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} name="Deteksi" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Species Distribution Donut */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-700">Species Distribution</h3>
                <span className="text-xs text-gray-400 border border-gray-200 px-2 py-0.5 rounded-lg">Pie</span>
              </div>
              {speciesDist.length > 0 ? (
                <div className="flex flex-col items-center">
                  <div className="relative w-full h-36">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={speciesDist} dataKey="count" nameKey="species" cx="50%" cy="50%" innerRadius={45} outerRadius={65} paddingAngle={2}>
                          {speciesDist.map((s: any, i: number) => (
                            <Cell key={s.species} fill={getColor(s.species, i)} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                      <span className="text-2xl font-bold text-gray-800">{speciesTotal}</span>
                      <span className="text-xs text-gray-400">Total</span>
                    </div>
                  </div>
                  <div className="w-full space-y-1 mt-2">
                    {speciesDist.map((s: any, i: number) => (
                      <div key={s.species} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getColor(s.species, i) }} />
                          <span className="text-gray-500">{s.species}</span>
                        </div>
                        <span className="text-gray-600 font-medium">{s.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-36 text-gray-300 text-sm">Belum ada data</div>
              )}
            </div>
          </div>

          {/* ── Deskripsi Misi ── */}
          {activeSession && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Deskripsi Misi</h3>
              <p className="text-sm text-gray-600">
                {activeSession.locationName} &nbsp;·&nbsp; {fmtDate(activeSession.startTime)},&nbsp;
                {fmtTimeRange(activeSession.startTime, activeSession.endTime)}
                {sessionDuration > 0 && <> &nbsp;·&nbsp; Durasi: {formatDuration(sessionDuration)}</>}
                {activeSession.locationName && <> &nbsp;·&nbsp; Lokasi: {activeSession.locationName}</>}
              </p>
              {(avgPh > 0 || avgTds > 0) && (
                <p className="text-xs text-gray-400 mt-1">
                  Kondisi perairan saat misi: TDS {avgTds > 300 ? 'tinggi' : 'normal'} ({avgTds} ppm),
                  DO {avgDo < 6 ? 'rendah' : 'normal'} ({avgDo} mg/L),
                  pH {avgPh < 6.5 ? 'rendah' : avgPh > 8.5 ? 'tinggi' : 'normal'} ({avgPh}),
                  Suhu {avgTemp < 26 || avgTemp > 30 ? 'perhatian' : 'normal'} ({avgTemp}°C)
                </p>
              )}
            </div>
          )}

          {/* ── Rata-rata Kualitas Air ── */}
          {(avgPh > 0 || avgTds > 0 || avgDo > 0 || avgTemp > 0) && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700">
                    💧 Rata-rata Kualitas Air — Misi {missionName}, {fmtDate(activeSession?.startTime ?? '')}
                  </h3>
                </div>
                <p className="text-xs text-gray-400">Nilai berikut merupakan rata-rata sensor selama sesi berlang</p>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { label: 'pH Air', value: avgPh, unit: 'pH', type: 'ph' as const },
                  { label: 'TDS', value: avgTds, unit: 'ppm', type: 'tds' as const },
                  { label: 'DO (Dissolved O₂)', value: avgDo, unit: 'mg/L', type: 'do' as const },
                  { label: 'Suhu Air', value: avgTemp, unit: '°C', type: 'temp' as const },
                ].map(({ label, value, unit, type }) => (
                  <div key={label} className="border border-gray-100 rounded-xl p-4">
                    <p className="text-xs text-gray-400 mb-1">{label}</p>
                    <div className="flex items-baseline gap-1 mb-2">
                      <span className={`text-3xl font-bold ${type === 'ph' ? getPhColor(value) : type === 'tds' ? getTdsColor(value) : type === 'do' ? getDoColor(value) : getTempColor(value)}`}>
                        {value.toFixed(1)}
                      </span>
                      <span className="text-xs text-gray-400">{unit}</span>
                    </div>
                    <StatusBadge value={value} type={type} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Detection Log Ikan ── */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">🐠 Detection Log — Ikan</h3>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">{totalDetections} deteksi tercatat</span>
                <button
                  onClick={async () => {
                    try {
                      const rows = await fetchAllRows(`/api/detections?session_id=${sessionId}`, detectionTotal)
                      downloadCSV(
                        rows,
                        `detection-log-${sessionLabel}.csv`,
                        ['TANGGAL', 'WAKTU MISI', 'SESSION ID', 'DURASI MISI', 'WAKTU DETEKSI', 'SPESIES', 'CONFIDENCE', 'KEDALAMAN'],
                        (r: any) => [
                          fmtDate(r.detectedAt),
                          fmtTimeRange(activeSession?.startTime ?? '', activeSession?.endTime ?? null),
                          sessionLabel,
                          sessionDuration > 0 ? formatDuration(sessionDuration) : '—',
                          new Date(r.detectedAt).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
                          r.speciesName,
                          `${(r.confidence * 100).toFixed(0)}%`,
                          r.depthAtDetection ? `${r.depthAtDetection}m` : '—',
                        ]
                      )
                    } catch {
                      toast.error('Gagal mengunduh CSV deteksi')
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  ↓ Download CSV
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    {['TANGGAL', 'WAKTU MISI', 'SESSION ID', 'DURASI MISI', 'WAKTU DETEKSI', 'SPESIES', 'CONFIDENCE', 'KEDALAMAN'].map(h => (
                      <th key={h} className="px-4 py-3 text-left font-semibold text-gray-400 tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {detectionList.length > 0 ? detectionList.map((r: any, i: number) => {
                    const conf = r.confidence ?? 0
                    const color = getColor(r.speciesName, i)
                    return (
                      <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmtDate(r.detectedAt)}</td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap font-mono">{fmtTimeRange(activeSession?.startTime ?? '', activeSession?.endTime ?? null)}</td>
                        <td className="px-4 py-3">
                          <span className="font-mono text-gray-400 border border-gray-200 px-2 py-0.5 rounded-lg bg-gray-50">{sessionLabel}</span>
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{sessionDuration > 0 ? formatDuration(sessionDuration) : '—'}</td>
                        <td className="px-4 py-3 text-gray-500 font-mono whitespace-nowrap">
                          {new Date(r.detectedAt).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 rounded text-white text-xs font-medium" style={{ backgroundColor: color }}>
                            {r.speciesName}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full rounded-full" style={{ width: `${conf * 100}%`, backgroundColor: color }} />
                            </div>
                            <span className="font-medium" style={{ color }}>{(conf * 100).toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-500">{r.depthAtDetection ? `${r.depthAtDetection}m` : '—'}</td>
                      </tr>
                    )
                  }) : (
                    <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-300">Belum ada data deteksi</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Detection Log Kualitas Air ── */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">💧 Detection Log — Kualitas Air</h3>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">Sensor data</span>
                <button
                  onClick={async () => {
                    try {
                      const rows = await fetchAllRows(`/api/telemetry?session_id=${sessionId}`, telemetryTotal)
                      downloadCSV(
                        rows,
                        `telemetry-log-${sessionLabel}.csv`,
                        ['TANGGAL', 'WAKTU MISI', 'SESSION ID', 'DURASI MISI', 'WAKTU SENSOR', 'PH', 'SUHU (C)', 'TDS (ppm)', 'DO (mg/L)'],
                        (r: any) => [
                          fmtDate(r.timestamp),
                          fmtTimeRange(activeSession?.startTime ?? '', activeSession?.endTime ?? null),
                          sessionLabel,
                          sessionDuration > 0 ? formatDuration(sessionDuration) : '—',
                          new Date(r.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
                          r.phLevel,
                          r.waterTemp,
                          r.tdsValue,
                          r.dissolvedOxygen,
                        ]
                      )
                    } catch {
                      toast.error('Gagal mengunduh CSV kualitas air')
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  ↓ Download CSV
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    {['TANGGAL', 'WAKTU MISI', 'SESSION ID', 'DURASI MISI', 'WAKTU SENSOR', 'PH', 'SUHU (°C)', 'TDS (ppm)', 'DO (mg/L)'].map(h => (
                      <th key={h} className="px-4 py-3 text-left font-semibold text-gray-400 tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {telemetryList.length > 0 ? telemetryList.map((r: any) => (
                    <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmtDate(r.timestamp)}</td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap font-mono">{fmtTimeRange(activeSession?.startTime ?? '', activeSession?.endTime ?? null)}</td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-gray-400 border border-gray-200 px-2 py-0.5 rounded-lg bg-gray-50">{sessionLabel}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{sessionDuration > 0 ? formatDuration(sessionDuration) : '—'}</td>
                      <td className="px-4 py-3 text-gray-500 font-mono whitespace-nowrap">
                        {new Date(r.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </td>
                      <td className={`px-4 py-3 font-medium ${getPhColor(r.phLevel)}`}>{r.phLevel?.toFixed(1)}</td>
                      <td className={`px-4 py-3 font-medium ${getTempColor(r.waterTemp)}`}>{r.waterTemp?.toFixed(1)}</td>
                      <td className={`px-4 py-3 font-medium ${getTdsColor(r.tdsValue)}`}>{r.tdsValue?.toFixed(0)}</td>
                      <td className={`px-4 py-3 font-medium ${getDoColor(r.dissolvedOxygen)}`}>{r.dissolvedOxygen?.toFixed(1)}</td>
                    </tr>
                  )) : (
                    <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-300">Belum ada data sensor</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Keterangan warna */}
            <div className="px-5 py-3 border-t border-gray-50 flex items-center gap-4 text-xs text-gray-500">
              <span>Keterangan warna sensor:</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Normal</span>
              <span className="flex items-center gap-1 text-red-500"><span className="w-2 h-2 rounded-full bg-red-500" /> Di Bawah Normal</span>
              <span className="flex items-center gap-1 text-yellow-500"><span className="w-2 h-2 rounded-full bg-yellow-400" /> Di Atas Normal</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}