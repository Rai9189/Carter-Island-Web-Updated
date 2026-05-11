'use client'

import { useState } from 'react'
import useSWR from 'swr'
import {
  Card, CardContent, CardHeader, CardTitle
} from '@/components/ui/card'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import {
  Fish, Droplets, Navigation, TrendingUp, Thermometer, Waves
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'

const fetcher = apiClient.swrFetcher

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#FF6B9D']

const TIME_RANGES = [
  { label: '24 Jam',  value: 24 },
  { label: '7 Hari',  value: 168 },
  { label: '30 Hari', value: 720 },
]

function fmtTime(t: string) {
  return new Date(t).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
}
function fmtDateTime(t: string) {
  return new Date(t).toLocaleString('id-ID')
}

export default function AnalyticsContent() {
  const [timeRange, setTimeRange]     = useState(24)
  const [sessionId, setSessionId]     = useState<string>('')
  const [dateFilter, setDateFilter]   = useState<string>('')

  // ── Ambil daftar semua sesi ──
  const { data: sessionsData } = useSWR('/api/analytics/sessions', fetcher)
  const sessions: any[] = (sessionsData as any)?.data || []

  // ── Analytics endpoints ──
  const detectionUrl = `/api/analytics/detections?hours=${timeRange}${sessionId ? `&session_id=${sessionId}` : ''}${dateFilter ? `&date=${dateFilter}` : ''}`
  const telemetryUrl = `/api/analytics/telemetry?hours=${timeRange}${sessionId ? `&session_id=${sessionId}` : ''}`
  const auvUrl       = `/api/analytics/auv-status?hours=${timeRange}${sessionId ? `&session_id=${sessionId}` : ''}`

  const { data: detectionData } = useSWR(detectionUrl, fetcher, { refreshInterval: 30000 })
  const { data: telemetryData } = useSWR(telemetryUrl, fetcher, { refreshInterval: 30000 })
  const { data: auvData }       = useSWR(auvUrl,       fetcher, { refreshInterval: 30000 })

  const detections = (detectionData as any)?.data
  const telemetry  = (telemetryData as any)?.data
  const auv        = (auvData as any)?.data

  return (
    <div className="space-y-6">

      {/* ── Filter Bar ── */}
      <div className="flex flex-wrap items-center gap-3">

        {/* Time range */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {TIME_RANGES.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setTimeRange(value)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                timeRange === value
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Filter by session */}
        <select
          value={sessionId}
          onChange={e => setSessionId(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white"
        >
          <option value="">Semua Sesi</option>
          {sessions.map((s: any) => (
            <option key={s.id} value={s.id}>
              {s.locationName} — {new Date(s.startTime).toLocaleDateString('id-ID')}
            </option>
          ))}
        </select>

        {/* Filter by date */}
        <input
          type="date"
          value={dateFilter}
          onChange={e => setDateFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white"
        />

        {/* Reset */}
        {(sessionId || dateFilter) && (
          <button
            onClick={() => { setSessionId(''); setDateFilter(''); }}
            className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 underline"
          >
            Reset Filter
          </button>
        )}
      </div>

      {/* ── Summary Cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Deteksi</p>
              <p className="text-2xl font-bold text-blue-600">
                {detections?.summary.totalDetections ?? 0}
              </p>
            </div>
            <Fish className="h-9 w-9 text-blue-400" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Spesies Unik</p>
              <p className="text-2xl font-bold text-green-600">
                {detections?.summary.uniqueSpecies ?? 0}
              </p>
            </div>
            <TrendingUp className="h-9 w-9 text-green-400" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Rata-rata pH</p>
              <p className="text-2xl font-bold text-teal-600">
                {telemetry?.summary.avgPh ?? '--'}
              </p>
            </div>
            <Droplets className="h-9 w-9 text-teal-400" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Rata-rata Suhu</p>
              <p className="text-2xl font-bold text-orange-600">
                {telemetry?.summary.avgTemp ? `${telemetry.summary.avgTemp}°C` : '--'}
              </p>
            </div>
            <Thermometer className="h-9 w-9 text-orange-400" />
          </div>
        </CardContent></Card>
      </div>

      {/* ── Fish Detection Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <Card>
          <CardHeader><CardTitle className="text-base">Deteksi Ikan per Waktu</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={detections?.timeSeries || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip labelFormatter={fmtDateTime} />
                <Legend />
                <Line type="monotone" dataKey="detections" stroke="#0088FE" name="Deteksi" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Distribusi Spesies</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={detections?.speciesDistribution || []}
                  dataKey="count"
                  nameKey="species"
                  cx="50%" cy="50%"
                  outerRadius={100}
                  label={({ species, percent }) =>
                    `${species} ${(percent * 100).toFixed(0)}%`
                  }
                >
                  {(detections?.speciesDistribution || []).map((_: any, i: number) => (
                    <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip /><Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* ── Water Quality Charts ── */}
      <div>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Kualitas Air
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* pH Trend */}
          <Card>
            <CardHeader><CardTitle className="text-base flex items-center gap-2">
              <Droplets className="h-4 w-4 text-blue-500" /> pH Level
            </CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={telemetry?.ph || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 11 }} />
                  <YAxis domain={[6, 10]} tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={fmtDateTime} />
                  <Legend />
                  <Line type="monotone" dataKey="value" stroke="#0088FE" name="pH" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* TDS Trend */}
          <Card>
            <CardHeader><CardTitle className="text-base flex items-center gap-2">
              <Waves className="h-4 w-4 text-teal-500" /> TDS (ppm)
            </CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={telemetry?.tds || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={fmtDateTime} />
                  <Legend />
                  <Line type="monotone" dataKey="value" stroke="#00C49F" name="TDS" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Dissolved Oxygen */}
          <Card>
            <CardHeader><CardTitle className="text-base">Dissolved Oxygen (mg/L)</CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={telemetry?.dissolvedOxygen || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={fmtDateTime} />
                  <Legend />
                  <Line type="monotone" dataKey="value" stroke="#FFBB28" name="DO" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Suhu Air */}
          <Card>
            <CardHeader><CardTitle className="text-base flex items-center gap-2">
              <Thermometer className="h-4 w-4 text-orange-500" /> Suhu Air (°C)
            </CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={telemetry?.temperature || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={fmtDateTime} />
                  <Legend />
                  <Line type="monotone" dataKey="value" stroke="#FF8042" name="Suhu" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── AUV Navigation Charts ── */}
      <div>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Navigasi ROV
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* Attitude */}
          <Card>
            <CardHeader><CardTitle className="text-base flex items-center gap-2">
              <Navigation className="h-4 w-4 text-indigo-500" /> Attitude (Roll/Pitch/Yaw)
            </CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={auv?.attitude || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={fmtDateTime} />
                  <Legend />
                  <Line type="monotone" dataKey="roll"  stroke="#8884D8" name="Roll"  dot={false} />
                  <Line type="monotone" dataKey="pitch" stroke="#82ca9d" name="Pitch" dot={false} />
                  <Line type="monotone" dataKey="yaw"   stroke="#ffc658" name="Yaw"   dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Depth & Speed */}
          <Card>
            <CardHeader><CardTitle className="text-base flex items-center gap-2">
              <Waves className="h-4 w-4 text-blue-500" /> Kedalaman & Kecepatan
            </CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={auv?.navigation || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tickFormatter={fmtTime} tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left"  tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={fmtDateTime} />
                  <Legend />
                  <Line yAxisId="left"  type="monotone" dataKey="depth" stroke="#0088FE" name="Depth (m)"   dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="speed" stroke="#FF8042" name="Speed (m/s)" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </div>

    </div>
  )
}