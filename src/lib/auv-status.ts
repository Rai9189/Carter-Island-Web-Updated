import { apiClient } from './api-client'

export interface AUVStatusUpdate {
  isOnline: boolean
  connectionStrength: 'Strong' | 'Moderate' | 'Weak' | 'Disconnected'
  uptimeSeconds: number
  locationStatus?: string
  lastStreamTime?: Date
}

export function calculateConnectionStrength(fps?: number, targetFps = 30): 'Strong' | 'Moderate' | 'Weak' | 'Disconnected' {
  if (!fps || fps === 0) return 'Disconnected'
  const ratio = fps / targetFps
  if (ratio >= 0.8) return 'Strong'
  if (ratio >= 0.5) return 'Moderate'
  return 'Weak'
}

export function calculateUptime(startTime: Date | null): number {
  if (!startTime) return 0
  return Math.floor((Date.now() - startTime.getTime()) / 1000)
}

export async function updateAUVStatus(status: AUVStatusUpdate): Promise<boolean> {
  try {
    await apiClient.post('/api/auv-status', status)
    return true
  } catch {
    return false
  }
}

export async function updateStreamConnected(startTime: Date): Promise<boolean> {
  return updateAUVStatus({ isOnline: true, connectionStrength: 'Strong', uptimeSeconds: calculateUptime(startTime), locationStatus: 'Active', lastStreamTime: new Date() })
}

export async function updateStreamDisconnected(): Promise<boolean> {
  return updateAUVStatus({ isOnline: false, connectionStrength: 'Disconnected', uptimeSeconds: 0, locationStatus: 'Active', lastStreamTime: new Date() })
}

export async function updateStreamPerformance(startTime: Date | null, fps: number, targetFps = 30): Promise<boolean> {
  return updateAUVStatus({ isOnline: startTime !== null, connectionStrength: calculateConnectionStrength(fps, targetFps), uptimeSeconds: calculateUptime(startTime), locationStatus: 'Active', lastStreamTime: startTime || undefined })
}