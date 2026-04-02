'use client'

import { useState } from 'react'
import useSWR from 'swr'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Fish, Activity, Wifi, TrendingUp } from 'lucide-react'
import { apiClient } from '@/lib/api-client'

/**
 * PERUBAHAN:
 * Sebelum: const fetcher = (url: string) => fetch(url).then(res => res.json())
 * Sesudah: fetcher = apiClient.swrFetcher
 *          → otomatis kirim JWT token ke FastAPI port 8000
 */
const fetcher = apiClient.swrFetcher

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8']

export default function AnalyticsContent() {
  const [timeRange, setTimeRange] = useState(24)

  const { data: detectionData } = useSWR(
    `/api/analytics/detections?hours=${timeRange}`,
    fetcher,
    { refreshInterval: 30000 }
  )

  const { data: telemetryData } = useSWR(
    `/api/analytics/telemetry?hours=${timeRange}`,
    fetcher,
    { refreshInterval: 30000 }
  )

  const { data: auvStatusData } = useSWR(
    `/api/analytics/auv-status?hours=${timeRange}`,
    fetcher,
    { refreshInterval: 30000 }
  )

  const detections = (detectionData as any)?.data
  const telemetry = (telemetryData as any)?.data
  const auvStatus = (auvStatusData as any)?.data

  return (
    <div className="space-y-6">
      {/* Time Range Selector */}
      <div className="flex gap-2">
        {[{ label: '24 Hours', value: 24 }, { label: '7 Days', value: 168 }].map(({ label, value }) => (
          <button key={value} onClick={() => setTimeRange(value)}
            className={`px-4 py-2 rounded-lg ${timeRange === value ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}>
            {label}
          </button>
        ))}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div><p className="text-sm text-gray-600">Total Detections</p><p className="text-2xl font-bold">{detections?.summary.totalDetections || 0}</p></div>
            <Fish className="h-10 w-10 text-blue-600" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div><p className="text-sm text-gray-600">Total Fish</p><p className="text-2xl font-bold">{detections?.summary.totalFish || 0}</p></div>
            <TrendingUp className="h-10 w-10 text-green-600" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div><p className="text-sm text-gray-600">Avg Battery</p><p className="text-2xl font-bold">{telemetry?.summary.avgBattery || 0}%</p></div>
            <Activity className="h-10 w-10 text-amber-600" />
          </div>
        </CardContent></Card>

        <Card><CardContent className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div><p className="text-sm text-gray-600">Uptime</p><p className="text-2xl font-bold">{auvStatus?.summary.uptimePercentage || 0}%</p></div>
            <Wifi className="h-10 w-10 text-purple-600" />
          </div>
        </CardContent></Card>
      </div>

      {/* Fish Detection Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Fish Detections Over Time</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={detections?.timeSeries || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tickFormatter={t => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                <YAxis />
                <Tooltip labelFormatter={t => new Date(t).toLocaleString()} />
                <Legend />
                <Line type="monotone" dataKey="fishCount" stroke="#0088FE" name="Fish Count" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Species Distribution</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={detections?.speciesDistribution || []} dataKey="count" nameKey="species" cx="50%" cy="50%" outerRadius={100} label>
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

      {/* Telemetry Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Battery Trends</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={telemetry?.battery || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tickFormatter={t => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                <YAxis /><Tooltip labelFormatter={t => new Date(t).toLocaleString()} /><Legend />
                <Line type="monotone" dataKey="remaining" stroke="#00C49F" name="Battery %" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Attitude Trends</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={telemetry?.attitude || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tickFormatter={t => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                <YAxis /><Tooltip labelFormatter={t => new Date(t).toLocaleString()} /><Legend />
                <Line type="monotone" dataKey="roll" stroke="#8884D8" name="Roll" />
                <Line type="monotone" dataKey="pitch" stroke="#82ca9d" name="Pitch" />
                <Line type="monotone" dataKey="yaw" stroke="#ffc658" name="Yaw" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* AUV Status Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Uptime History</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={auvStatus?.uptimeHistory || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tickFormatter={t => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                <YAxis /><Tooltip labelFormatter={t => new Date(t).toLocaleString()} /><Legend />
                <Line type="monotone" dataKey="uptime" stroke="#FF8042" name="Uptime (min)" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Connection Quality</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={auvStatus?.connectionDistribution || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="status" /><YAxis /><Tooltip /><Legend />
                <Bar dataKey="count" fill="#8884D8" name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}