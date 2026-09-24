'use client'

import useSWR from 'swr'
import { useRouter } from 'next/navigation'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { apiClient, isApiStatus } from '@/lib/api-client'
import {
  Sailboat,
  CalendarDays,
  Timer,
  MapPin,
  Droplets,
  Zap,
  Wind,
  Thermometer,
  ChevronRight,
  Gauge,
  Navigation,
  Activity,
  Anchor,
} from 'lucide-react'

const fetcher = apiClient.swrFetcher

function getPhStatus(ph: number) {
  if (ph < 7.5) return { label: 'Rendah', color: 'text-red-500', bar: 'bg-red-500' }
  if (ph > 8.4) return { label: 'Tinggi', color: 'text-yellow-500', bar: 'bg-yellow-500' }
  return { label: 'Normal', color: 'text-green-500', bar: 'bg-green-500' }
}

function getTdsStatus(tds: number) {
  if (tds < 200) return { label: 'Rendah', color: 'text-blue-500', bar: 'bg-blue-500' }
  if (tds > 500) return { label: 'Tinggi', color: 'text-red-500', bar: 'bg-red-500' }
  return { label: 'Normal', color: 'text-yellow-500', bar: 'bg-yellow-500' }
}

function getDoStatus(doVal: number) {
  if (doVal < 5) return { label: 'Rendah', color: 'text-red-500', bar: 'bg-red-500' }
  if (doVal > 8) return { label: 'Tinggi', color: 'text-blue-500', bar: 'bg-blue-500' }
  return { label: 'Normal', color: 'text-green-500', bar: 'bg-green-500' }
}

function getTempStatus(temp: number) {
  if (temp < 20) return { label: 'Dingin', color: 'text-blue-500', bar: 'bg-blue-500' }
  if (temp > 32) return { label: 'Panas', color: 'text-red-500', bar: 'bg-red-500' }
  return { label: 'Normal', color: 'text-green-500', bar: 'bg-green-500' }
}

function progressPercent(value: number, max: number) {
  return Math.min(100, Math.max(0, (value / max) * 100))
}

function InfoCard({
  label, value, icon: Icon, iconBg,
}: {
  label: string; value: string; icon: React.ElementType; iconBg: string
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4 flex items-center justify-between">
      <div>
        <p className="text-xs text-gray-400 mb-1">{label}</p>
        <p className="text-lg font-bold text-gray-800 leading-tight">{value}</p>
      </div>
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${iconBg}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
    </div>
  )
}

function WaterCard({
  label, value, unit, status, barPercent, icon: Icon, iconColor,
}: {
  label: string; value: string; unit: string
  status: { label: string; color: string; bar: string }
  barPercent: number; icon: React.ElementType; iconColor: string
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-400">{label}</p>
        <Icon className={`w-4 h-4 ${iconColor}`} />
      </div>
      <div className="flex items-baseline gap-1 mb-1">
        <span className="text-2xl font-bold text-gray-800">{value}</span>
        <span className="text-xs text-gray-400">{unit}</span>
      </div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className={`text-xs font-medium ${status.color} flex items-center gap-0.5`}>
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${status.bar}`} />
          {status.label}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${status.bar}`} style={{ width: `${barPercent}%` }} />
      </div>
    </div>
  )
}

const SPECIES_COLORS = ['#3b82f6', '#22c55e', '#f97316', '#9ca3af']

interface DashboardContentProps {
  userFullName: string
  userRole: string
}

export default function DashboardContent({ userFullName, userRole }: DashboardContentProps) {
  const router = useRouter()

  // Coba sesi RUNNING dulu (livestream aktif), fallback ke sesi COMPLETED terakhir
  const { data: activeSessionData, error: activeSessionError } = useSWR(
    '/api/sessions/active',
    fetcher,
    { refreshInterval: 5000, shouldRetryOnError: false, errorRetryCount: 0, revalidateOnFocus: false }
  )
  const hasRunning = !!(activeSessionData as any)?.data
  const { data: completedSessionData, error: completedSessionError, isLoading: sessionLoading } = useSWR(
    hasRunning ? null : '/api/sessions?limit=1&sort=desc&status_filter=Completed',
    fetcher,
    { refreshInterval: 30000, revalidateOnFocus: false }
  )

  const session = hasRunning
    ? (activeSessionData as any)?.data
    : (() => {
        const raw = (completedSessionData as any)?.data
        return Array.isArray(raw) ? raw[0] : raw
      })()

  // Telemetri & AUV harus dari sesi yang sama dengan info misi di atas, bukan baris terbaru global
  const { data: telemetryData } = useSWR(
    session?.id ? `/api/telemetry/latest?session_id=${session.id}` : null,
    fetcher,
    { refreshInterval: 5000, revalidateOnFocus: false }
  )
  const { data: auvData } = useSWR(
    session?.id ? `/api/auv-status/latest?session_id=${session.id}` : null,
    fetcher,
    { refreshInterval: 5000, revalidateOnFocus: false }
  )
  const { data: fishData } = useSWR(
    session?.id ? `/api/fish-counts/session/${session.id}` : null,
    fetcher,
    { refreshInterval: 5000, revalidateOnFocus: false }
  )
  const telemetry = (telemetryData as any)?.data
  const auv = (auvData as any)?.data
  const fishRaw = (fishData as any)?.data

  // Loading state
  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <div className="w-8 h-8 border-2 border-gray-200 border-t-blue-400 rounded-full animate-spin" />
          <p className="text-sm">Memuat data...</p>
        </div>
      </div>
    )
  }

  // Error state — gagal menghubungi server (404 di /sessions/active = memang tidak ada sesi aktif)
  const sessionFetchFailed = [activeSessionError, completedSessionError]
    .some(err => err && !isApiStatus(err, 404))
  if (!session && sessionFetchFailed) {
    return (
      <div className="flex flex-col items-center justify-center h-80 text-center">
        <div className="w-20 h-20 rounded-full bg-blue-50 flex items-center justify-center mb-4">
          <Anchor className="w-9 h-9 text-blue-300" />
        </div>
        <h3 className="text-lg font-semibold text-gray-600 mb-1">Gagal Memuat Data</h3>
        <p className="text-sm text-gray-400 max-w-xs">
          Periksa koneksi ke server. Data akan dimuat ulang otomatis.
        </p>
      </div>
    )
  }

  // Empty state — belum ada misi sama sekali
  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center h-80 text-center">
        <div className="w-20 h-20 rounded-full bg-blue-50 flex items-center justify-center mb-4">
          <Anchor className="w-9 h-9 text-blue-300" />
        </div>
        <h3 className="text-lg font-semibold text-gray-600 mb-1">Belum Ada Misi</h3>
        <p className="text-sm text-gray-400 max-w-xs">
          Dashboard akan menampilkan data setelah misi pertama dimulai.
        </p>
      </div>
    )
  }

  // Ada misi — tampilkan semua data
  const ph = telemetry?.phLevel ?? 0
  const tds = telemetry?.tdsValue ?? 0
  const doVal = telemetry?.dissolvedOxygen ?? 0
  const temp = telemetry?.waterTemp ?? 0

  const misiTerakhir = session.locationName ?? '—'
  const tanggalMisi = session.startTime
    ? new Date(session.startTime).toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' })
    : '—'
  const durasi = (() => {
    if (!session.startTime) return '—'
    const end = session.endTime ? new Date(session.endTime) : new Date()
    const diffMs = end.getTime() - new Date(session.startTime).getTime()
    if (diffMs <= 0) return '—'
    const h = Math.floor(diffMs / 3600000)
    const m = Math.floor((diffMs % 3600000) / 60000)
    const s = Math.floor((diffMs % 60000) / 1000)
    return h > 0 ? `${h}j ${String(m).padStart(2,'0')}m` : `${m}m ${String(s).padStart(2,'0')}d`
  })()
  const lokasi = session.locationName ?? '—'

  const speciesCounts: Array<{speciesName: string; totalCount: number}> = Array.isArray(fishRaw?.counts) ? fishRaw.counts : []
  const speciesTotal: number = fishRaw?.totalFish ?? 0
  const speciesChartData = speciesCounts.map(c => ({ name: c.speciesName, value: c.totalCount }))
  const hasSpeciesData = speciesChartData.length > 0

  const sensorHealth = [
    { label: 'Gyroscope', ok: !!auv?.gyroscope },
    { label: 'Accelerometer', ok: !!auv?.accelerometer },
    { label: 'Magnetometer', ok: !!auv?.magnetometer },
  ]

  return (
    <div className="space-y-4">

      {/* Row 1: Info Misi */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <InfoCard label="Misi Terakhir" value={misiTerakhir} icon={Sailboat} iconBg="bg-blue-400" />
        <InfoCard label="Tanggal, Waktu" value={tanggalMisi} icon={CalendarDays} iconBg="bg-teal-400" />
        <InfoCard label="Durasi" value={durasi} icon={Timer} iconBg="bg-yellow-400" />
        <InfoCard label="Lokasi Misi" value={lokasi} icon={MapPin} iconBg="bg-red-400" />
      </div>

      {/* Row 2: Water Quality */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <WaterCard label="pH Air" value={ph.toFixed(1)} unit="pH" status={getPhStatus(ph)} barPercent={progressPercent(ph, 14)} icon={Droplets} iconColor="text-blue-400" />
        <WaterCard label="TDS" value={tds.toFixed(0)} unit="ppm" status={getTdsStatus(tds)} barPercent={progressPercent(tds, 1000)} icon={Zap} iconColor="text-yellow-400" />
        <WaterCard label="DO (Dissolved Oxygen)" value={doVal.toFixed(1)} unit="mg/L" status={getDoStatus(doVal)} barPercent={progressPercent(doVal, 15)} icon={Wind} iconColor="text-red-400" />
        <WaterCard label="Suhu Air" value={temp.toFixed(1)} unit="°C" status={getTempStatus(temp)} barPercent={progressPercent(temp, 50)} icon={Thermometer} iconColor="text-green-400" />
      </div>

      {/* Row 3: Telemetry + Species */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">

        {/* Telemetry Data */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-700 flex items-center gap-2">
              <Navigation className="w-4 h-4 text-blue-500" />
              Telemetry Data
            </h2>
            <button
              onClick={() => router.push('/dashboard/recordings')}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg flex items-center gap-1 transition-colors"
            >
              Buka Recording <ChevronRight className="w-3 h-3" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="bg-gray-50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Gauge className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-medium text-gray-600">Attitude</span>
              </div>
              <div className="space-y-2">
                {[
                  { label: 'Roll', value: auv?.roll != null ? `${auv.roll.toFixed(1)}°` : '—' },
                  { label: 'Pitch', value: auv?.pitch != null ? `${auv.pitch.toFixed(1)}°` : '—' },
                  { label: 'Yaw', value: auv?.yaw != null ? `${auv.yaw.toFixed(0)}°` : '—' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between items-center text-sm">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-semibold text-gray-800">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <MapPin className="w-4 h-4 text-red-400" />
                <span className="text-sm font-medium text-gray-600">Posisi</span>
              </div>
              <div className="space-y-2">
                {[
                  { label: 'Depth', value: auv?.depth != null ? `${auv.depth.toFixed(1)} m` : '—' },
                  { label: 'Heading', value: auv?.heading ?? '—' },
                  { label: 'Speed', value: auv?.speed != null ? `${auv.speed.toFixed(1)} kts` : '—' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between items-center text-sm">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-semibold text-gray-800">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="md:col-span-2 bg-gray-50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-medium text-gray-600">Health</span>
              </div>
              <div className="space-y-2">
                {sensorHealth.map(({ label, ok }) => (
                  <div key={label} className="flex justify-between items-center text-sm">
                    <span className="text-gray-500">{label}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${ok ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'}`}>
                      {ok ? 'OK' : 'N/A'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Species Distribution */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <h2 className="font-semibold text-gray-700 mb-4">Species Distribution</h2>
          {hasSpeciesData ? (
            <div className="flex flex-col items-center">
              <div className="relative w-full h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={speciesChartData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2} dataKey="value" startAngle={90} endAngle={-270}>
                      {speciesChartData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={SPECIES_COLORS[index % SPECIES_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', fontSize: '12px' }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-3xl font-bold text-gray-800">{speciesTotal}</span>
                  <span className="text-xs text-gray-400">Total</span>
                </div>
              </div>
              <div className="w-full space-y-1.5 mt-2">
                {speciesChartData.map((entry, index) => (
                  <div key={entry.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: SPECIES_COLORS[index % SPECIES_COLORS.length] }} />
                      <span className="text-gray-600">{entry.name}</span>
                    </div>
                    <span className="font-medium text-gray-700">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-52">
              <div className="w-20 h-20 rounded-full border-4 border-dashed border-gray-200 flex items-center justify-center mb-3">
                <span className="text-3xl">🐟</span>
              </div>
              <p className="text-sm text-gray-400">Belum ada data deteksi</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}