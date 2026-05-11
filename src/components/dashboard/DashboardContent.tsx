'use client';

import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Activity,
  Droplets,
  Thermometer,
  Navigation,
  Compass,
  Gauge,
  MapPin,
  Waves,
  Wind,
} from 'lucide-react';
import MapButton from '@/components/ui/MapButton';
import { apiClient } from '@/lib/api-client';

const fetcher = apiClient.swrFetcher;

/**
 * Warna indikator pH air laut:
 *  < 7.5  → asam (merah)
 *  7.5–8.4 → normal (hijau)
 *  > 8.4  → basa (kuning)
 */
function getPhColor(ph: number) {
  if (ph < 7.5) return { text: 'text-red-600', bg: 'bg-red-100' };
  if (ph > 8.4) return { text: 'text-yellow-600', bg: 'bg-yellow-100' };
  return { text: 'text-green-600', bg: 'bg-green-100' };
}

/**
 * Warna indikator dissolved oxygen:
 *  < 5 mg/L → rendah (merah)
 *  5–8      → normal (hijau)
 *  > 8      → tinggi (biru)
 */
function getDoColor(doVal: number) {
  if (doVal < 5) return 'text-red-600';
  if (doVal > 8) return 'text-blue-600';
  return 'text-green-600';
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
   * Telemetry → data kualitas air (ph_level, tds_value, dissolved_oxygen, water_temp, depth)
   * AUV Status → data navigasi ROV (roll, pitch, yaw, depth, heading, speed)
   */
  const { data: telemetryData, error: telemetryError } = useSWR(
    '/api/telemetry/latest',
    fetcher,
    { refreshInterval: 2000, revalidateOnFocus: true }
  );

  const { data: auvData, error: auvError } = useSWR(
    '/api/auv-status/latest',
    fetcher,
    { refreshInterval: 2000, revalidateOnFocus: true }
  );

  const telemetry = (telemetryData as any)?.data;
  const auv       = (auvData as any)?.data;
  const isLoading = !telemetry && !auv && !telemetryError && !auvError;

  const phColor = telemetry ? getPhColor(telemetry.phLevel) : { text: 'text-gray-500', bg: 'bg-gray-100' };

  return (
    <>
      {/* ── Stats Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">

        {/* pH Air */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">pH Air</p>
                <p className={`text-2xl font-bold ${phColor.text}`}>
                  {isLoading ? '...' : telemetry ? telemetry.phLevel.toFixed(2) : '--'}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">Normal: 7.5–8.4</p>
              </div>
              <div className={`w-11 h-11 ${phColor.bg} rounded-xl flex items-center justify-center`}>
                <Droplets className={`w-5 h-5 ${phColor.text}`} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Suhu Air */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">Suhu Air</p>
                <p className="text-2xl font-bold text-orange-600">
                  {isLoading ? '...' : telemetry ? `${telemetry.waterTemp.toFixed(1)}°C` : '--'}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">Sensor ROV</p>
              </div>
              <div className="w-11 h-11 bg-orange-100 rounded-xl flex items-center justify-center">
                <Thermometer className="w-5 h-5 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Kedalaman */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">Kedalaman</p>
                <p className="text-2xl font-bold text-blue-600">
                  {isLoading ? '...' : auv ? `${auv.depth.toFixed(1)}m` : '--'}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">IMU Pixhawk</p>
              </div>
              <div className="w-11 h-11 bg-blue-100 rounded-xl flex items-center justify-center">
                <Waves className="w-5 h-5 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Kecepatan */}
        <Card className="border-0 shadow-sm">
          <CardContent className="px-6 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">Kecepatan</p>
                <p className="text-2xl font-bold text-purple-600">
                  {isLoading ? '...' : auv ? `${auv.speed.toFixed(1)} m/s` : '--'}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">Sensor ROV</p>
              </div>
              <div className="w-11 h-11 bg-purple-100 rounded-xl flex items-center justify-center">
                <Wind className="w-5 h-5 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Main Content ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Kiri: Telemetri lengkap */}
        <div className="lg:col-span-2 space-y-4">

          {/* Water Quality */}
          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Droplets className="h-5 w-5 text-blue-600" />
                Kualitas Air — Live Sensor
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">

                {/* pH */}
                <div className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl border border-blue-200">
                  <p className="text-xs font-medium text-blue-600 mb-1">pH Level</p>
                  <p className={`text-2xl font-bold ${phColor.text}`}>
                    {telemetry ? telemetry.phLevel.toFixed(2) : '--'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Ideal: 7.5–8.4</p>
                </div>

                {/* TDS */}
                <div className="p-4 bg-gradient-to-br from-teal-50 to-teal-100 rounded-xl border border-teal-200">
                  <p className="text-xs font-medium text-teal-600 mb-1">TDS</p>
                  <p className="text-2xl font-bold text-teal-700">
                    {telemetry ? `${telemetry.tdsValue.toFixed(0)}` : '--'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">ppm</p>
                </div>

                {/* Dissolved Oxygen */}
                <div className="p-4 bg-gradient-to-br from-cyan-50 to-cyan-100 rounded-xl border border-cyan-200">
                  <p className="text-xs font-medium text-cyan-600 mb-1">Dissolved O₂</p>
                  <p className={`text-2xl font-bold ${telemetry ? getDoColor(telemetry.dissolvedOxygen) : 'text-gray-400'}`}>
                    {telemetry ? telemetry.dissolvedOxygen.toFixed(1) : '--'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">mg/L</p>
                </div>

                {/* Suhu */}
                <div className="p-4 bg-gradient-to-br from-orange-50 to-orange-100 rounded-xl border border-orange-200">
                  <p className="text-xs font-medium text-orange-600 mb-1">Suhu Air</p>
                  <p className="text-2xl font-bold text-orange-700">
                    {telemetry ? telemetry.waterTemp.toFixed(1) : '--'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">°C</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* AUV Navigation */}
          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Navigation className="h-5 w-5 text-indigo-600" />
                Navigasi ROV — IMU Pixhawk
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">

                {/* Attitude */}
                <div className="p-4 bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl border border-indigo-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Gauge className="h-4 w-4 text-indigo-600" />
                    <p className="text-xs font-semibold text-indigo-700">Attitude</p>
                  </div>
                  <div className="space-y-1 text-sm">
                    {[
                      { label: 'Roll',  value: auv?.roll },
                      { label: 'Pitch', value: auv?.pitch },
                      { label: 'Yaw',   value: auv?.yaw },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex justify-between">
                        <span className="text-gray-500">{label}</span>
                        <span className="font-medium text-gray-800">
                          {value != null ? `${value.toFixed(1)}°` : '--'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Heading & Depth */}
                <div className="p-4 bg-gradient-to-br from-violet-50 to-violet-100 rounded-xl border border-violet-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Compass className="h-4 w-4 text-violet-600" />
                    <p className="text-xs font-semibold text-violet-700">Heading & Depth</p>
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Heading</span>
                      <span className="font-bold text-violet-700">
                        {auv?.heading ?? '--'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Depth</span>
                      <span className="font-medium text-gray-800">
                        {auv ? `${auv.depth.toFixed(1)}m` : '--'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Speed</span>
                      <span className="font-medium text-gray-800">
                        {auv ? `${auv.speed.toFixed(1)} m/s` : '--'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Sensor IMU */}
                <div className="p-4 bg-gradient-to-br from-slate-50 to-slate-100 rounded-xl border border-slate-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="h-4 w-4 text-slate-600" />
                    <p className="text-xs font-semibold text-slate-700">Sensor IMU</p>
                  </div>
                  <div className="space-y-1.5 text-sm">
                    {[
                      { label: 'Gyroscope',     value: auv?.gyroscope },
                      { label: 'Accelerometer', value: auv?.accelerometer },
                      { label: 'Magnetometer',  value: auv?.magnetometer },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex justify-between items-center">
                        <span className="text-gray-500 text-xs">{label}</span>
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          value
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-400'
                        }`}>
                          {value ? 'Active' : 'N/A'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Kanan: Peta Lokasi */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <MapPin className="h-5 w-5 text-purple-600" />
              Lokasi Survei
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Map embed */}
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

              {/* Info navigasi ringkas */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Depth</span>
                    <span className="font-semibold text-blue-600">
                      {auv ? `${auv.depth.toFixed(1)}m` : '--'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Speed</span>
                    <span className="font-medium text-gray-800">
                      {auv ? `${auv.speed.toFixed(1)} m/s` : '--'}
                    </span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Heading</span>
                    <span className="font-semibold text-violet-600">
                      {auv?.heading ?? '--'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">pH</span>
                    <span className={`font-semibold ${phColor.text}`}>
                      {telemetry ? telemetry.phLevel.toFixed(2) : '--'}
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