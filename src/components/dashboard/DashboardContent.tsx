'use client';

import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Activity,
  Wifi,
  Clock,
  MapPin,
  Battery,
  Gauge,
} from 'lucide-react';
import MapButton from '@/components/ui/MapButton';
import { apiClient } from '@/lib/api-client';

// SWR fetcher pakai apiClient — otomatis kirim JWT token
const fetcher = apiClient.swrFetcher;

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function getConnectionColor(strength: string) {
  switch (strength.toLowerCase()) {
    case 'strong':
      return { bg: 'bg-green-100', text: 'text-green-600' };
    case 'moderate':
      return { bg: 'bg-yellow-100', text: 'text-yellow-600' };
    case 'weak':
      return { bg: 'bg-red-100', text: 'text-red-600' };
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-600' };
  }
}

interface DashboardContentProps {
  userFullName: string;
  userRole: string;
}

export default function DashboardContent({
  userFullName,
  userRole,
}: DashboardContentProps) {
  /**
   * PERUBAHAN:
   * - URL berubah dari '/api/telemetry/latest' ke '/api/telemetry/latest'
   *   (sama, tapi sekarang fetcher mengarah ke FastAPI port 8000)
   * - fetcher diganti dari fetch() biasa ke apiClient.swrFetcher
   *   yang otomatis kirim JWT token
   * - HAPUS: useEffect polling /api/health/check
   *   Sudah tidak perlu karena health check jalan otomatis di server (Fase 5)
   */
  const { data: telemetryData, error: telemetryError } = useSWR(
    '/api/telemetry/latest',
    fetcher,
    {
      refreshInterval: 2000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );

  const { data: auvData, error: auvError } = useSWR(
    '/api/auv-status/latest',
    fetcher,
    {
      refreshInterval: 3000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );

  // HAPUS: useEffect polling /api/health/check
  // Health check sekarang jalan otomatis di server via APScheduler (Fase 5)
  // Frontend cukup baca hasilnya dari /api/auv-status/latest

  const telemetry = (telemetryData as any)?.data;
  const auvStatus = (auvData as any)?.data;
  const isLoading = !telemetry && !auvStatus && !telemetryError && !auvError;

  const connectionColor = auvStatus
    ? getConnectionColor(auvStatus.connectionStrength)
    : { bg: 'bg-blue-100', text: 'text-blue-600' };

  return (
    <>
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {/* AUV Status */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">AUV Status</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {isLoading ? 'Loading...' : auvStatus?.isOnline ? 'Online' : 'Offline'}
                </p>
              </div>
              <div className={`w-12 h-12 ${auvStatus?.isOnline ? 'bg-green-100' : 'bg-gray-100'} rounded-xl flex items-center justify-center`}>
                <Activity className={`w-6 h-6 ${auvStatus?.isOnline ? 'text-green-600' : 'text-gray-600'}`} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Connection */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Connection</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {isLoading ? 'Loading...' : auvStatus?.connectionStrength || 'Unknown'}
                </p>
              </div>
              <div className={`w-12 h-12 ${connectionColor.bg} rounded-xl flex items-center justify-center`}>
                <Wifi className={`w-6 h-6 ${connectionColor.text}`} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Uptime */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Uptime</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {isLoading ? 'Loading...' : auvStatus ? formatUptime(auvStatus.uptimeSeconds) : '0h 0m'}
                </p>
              </div>
              <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                <Clock className="w-6 h-6 text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Location */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Location</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {isLoading ? 'Loading...' : auvStatus?.locationStatus || 'Active'}
                </p>
              </div>
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                <MapPin className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Telemetry Data */}
        <Card className="lg:col-span-2 border-0 shadow-sm">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Activity className="h-5 w-5 text-blue-600" />
              Live Telemetry
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Attitude */}
              <div className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl border border-blue-200">
                <div className="flex items-center gap-2 mb-2">
                  <Gauge className="h-5 w-5 text-blue-600" />
                  <h3 className="font-semibold text-gray-900">Attitude</h3>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Roll</span>
                    <span className="font-medium">
                      {telemetry ? `${telemetry.rollDeg.toFixed(1)}°` : '--'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Pitch</span>
                    <span className="font-medium">
                      {telemetry ? `${telemetry.pitchDeg.toFixed(1)}°` : '--'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Yaw</span>
                    <span className="font-medium">
                      {telemetry ? `${telemetry.yawDeg.toFixed(1)}°` : '--'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Compass */}
              <div className="p-4 bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl border border-indigo-200">
                <div className="flex items-center gap-2 mb-2">
                  <MapPin className="h-5 w-5 text-indigo-600" />
                  <h3 className="font-semibold text-gray-900">Compass</h3>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Heading</span>
                    <span className="font-bold text-2xl text-indigo-600">
                      {telemetry ? `${telemetry.headingDeg.toFixed(1)}°` : '--'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Battery */}
              <div className="p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-xl border border-green-200">
                <div className="flex items-center gap-2 mb-2">
                  <Battery className="h-5 w-5 text-green-600" />
                  <h3 className="font-semibold text-gray-900">Battery</h3>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Level</span>
                    <span className="font-semibold text-green-600">
                      {telemetry ? `${telemetry.remainingPercent.toFixed(0)}%` : '--'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Voltage</span>
                    <span className="font-medium">
                      {telemetry ? `${telemetry.voltageV.toFixed(2)}V` : '--'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Current</span>
                    <span className="font-medium">
                      {telemetry?.currentA != null ? `${telemetry.currentA.toFixed(2)}A` : '--'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Health */}
              <div className="p-4 bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl border border-purple-200">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="h-5 w-5 text-purple-600" />
                  <h3 className="font-semibold text-gray-900">Health</h3>
                </div>
                <div className="space-y-1 text-sm">
                  {[
                    { label: 'Gyroscope', key: 'gyroCal' },
                    { label: 'Accelerometer', key: 'accelCal' },
                    { label: 'Magnetometer', key: 'magCal' },
                  ].map(({ label, key }) => (
                    <div key={key} className="flex justify-between items-center">
                      <span className="text-gray-600">{label}</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        telemetry?.[key]
                          ? 'bg-green-200 text-green-800'
                          : 'bg-red-200 text-red-800'
                      }`}>
                        {telemetry ? (telemetry[key] ? 'OK' : 'BAD') : '--'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* AUV Location Map */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-0">
            <CardTitle className="flex items-center gap-2 text-lg">
              <MapPin className="h-5 w-5 text-purple-600" />
              AUV Detail Location
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="w-full h-48 rounded-xl overflow-hidden border border-gray-200 relative">
                <iframe
                  src="https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d3961.785!2d110.63642!3d-6.62177!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f15.1!5e0!3m2!1sen!2sid!4v1699123456789!5m2!1sen!2sid"
                  width="100%"
                  height="100%"
                  style={{ border: 0 }}
                  allowFullScreen
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                  className="rounded-xl"
                />
                <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10">
                  <div className="relative flex items-center justify-center">
                    <div className="absolute w-6 h-6 bg-red-500 rounded-full animate-ping opacity-75" />
                    <div className="absolute w-4 h-4 bg-red-500 rounded-full animate-pulse" />
                    <div className="relative w-2 h-2 bg-red-600 rounded-full" />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Depth</span>
                    <span className="font-medium text-gray-900">15.2m</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Speed</span>
                    <span className="font-medium text-gray-900">2.3 kts</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Heading</span>
                    <span className="font-medium text-gray-900">
                      {telemetry ? `${telemetry.headingDeg.toFixed(0)}°` : '--'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Battery</span>
                    <span className={`font-medium ${
                      telemetry?.remainingPercent > 50
                        ? 'text-green-600'
                        : telemetry?.remainingPercent > 20
                        ? 'text-yellow-600'
                        : 'text-red-600'
                    }`}>
                      {telemetry ? `${telemetry.remainingPercent.toFixed(0)}%` : '--'}
                    </span>
                  </div>
                </div>
              </div>

              <MapButton lat={-6.621770076466091} lng={110.64180349373554} className="w-full">
                View Full Map
              </MapButton>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}