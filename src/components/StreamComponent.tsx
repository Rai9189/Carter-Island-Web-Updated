'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { toast } from 'sonner'
import Header from '@/components/layout/Header'
import { apiClient } from '@/lib/api-client'
import useSWR from 'swr'

const IFRAME_PREVIEW_URL = process.env.NEXT_PUBLIC_STREAM_PREVIEW_URL || 'http://192.168.2.2:8889/cam/'
const API_WS_URL = process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'
const SPECIES_COLORS: Record<string, string> = {
  Kerapu: '#3b82f6',
  Bandeng: '#22c55e',
  Teri: '#f59e0b',
  Pindang: '#f97316',
  'Lainnya / Unknown': '#9ca3af',
}

type ConnStatus = 'disconnected' | 'connected' | 'error'
type Profile = 'balanced' | 'ultra'
type Codec = 'h264' | 'vp8'
type SourceMode = 'server' | 'device'

interface ActiveSession { id: string; locationName: string; startTime: string; status: string }
interface SpeciesCount { speciesName: string; totalCount: number }
interface DetectionLog { time: string; species: string; confidence: number; frame: number }
interface PerformanceData { fps?: number; inference_fps?: number; active_ws?: number; model_loaded?: boolean; device?: string }
interface ModelInfo { model_loaded: boolean; device?: string }

// ── Helpers ──────────────────────────────────────────────────────────────────
function getPhStatus(ph: number) {
  if (ph === 0) return { label: 'No Data', color: 'text-gray-400', bar: 'bg-gray-300', dot: 'bg-gray-400' }
  if (ph < 6.5) return { label: 'Rendah', color: 'text-red-500', bar: 'bg-red-500', dot: 'bg-red-500' }
  if (ph > 8.5) return { label: 'Tinggi', color: 'text-yellow-500', bar: 'bg-yellow-500', dot: 'bg-yellow-500' }
  return { label: 'Normal', color: 'text-green-500', bar: 'bg-green-500', dot: 'bg-green-500' }
}
function getTdsStatus(tds: number) {
  if (tds === 0) return { label: 'No Data', color: 'text-gray-400', bar: 'bg-gray-300', dot: 'bg-gray-400' }
  if (tds > 300) return { label: 'Tinggi', color: 'text-yellow-500', bar: 'bg-yellow-500', dot: 'bg-yellow-500' }
  return { label: 'Normal', color: 'text-green-500', bar: 'bg-green-500', dot: 'bg-green-500' }
}
function getDoStatus(doVal: number) {
  if (doVal === 0) return { label: 'No Data', color: 'text-gray-400', bar: 'bg-gray-300', dot: 'bg-gray-400' }
  if (doVal < 6.0) return { label: 'Rendah', color: 'text-red-500', bar: 'bg-red-500', dot: 'bg-red-500' }
  return { label: 'Normal', color: 'text-green-500', bar: 'bg-green-500', dot: 'bg-green-500' }
}
function getTempStatus(temp: number) {
  if (temp === 0) return { label: 'No Data', color: 'text-gray-400', bar: 'bg-gray-300', dot: 'bg-gray-400' }
  if (temp < 26 || temp > 30) return { label: 'Perhatian', color: 'text-yellow-500', bar: 'bg-yellow-500', dot: 'bg-yellow-500' }
  return { label: 'Normal', color: 'text-green-500', bar: 'bg-green-500', dot: 'bg-green-500' }
}
function progressPct(v: number, max: number) { return Math.min(100, Math.max(0, (v / max) * 100)) }
function formatDuration(seconds: number) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
function getSpeciesColor(name: string, idx: number) {
  return SPECIES_COLORS[name] || Object.values(SPECIES_COLORS)[idx % Object.values(SPECIES_COLORS).length] || '#6366f1'
}

// ── Reusable select style ─────────────────────────────────────────────────────
const selectCls = (disabled: boolean) =>
  `border border-gray-200 rounded-lg px-3 py-1.5 text-xs text-gray-700 bg-white focus:outline-none focus:border-blue-400 transition-colors ${disabled ? 'opacity-50 cursor-not-allowed bg-gray-50' : 'cursor-pointer hover:border-gray-300'}`

// ── Mission Save Dialog — muncul saat Stop Stream ────────────────────────────
function MissionSaveDialog({ duration, onSave, isSaving }: {
  duration: string
  onSave: (missionName: string, locationName: string) => void
  isSaving?: boolean
}) {
  const [missionName, setMissionName] = useState('')
  const [locationName, setLocationName] = useState('')
  const [errors, setErrors] = useState<{ missionName?: string; locationName?: string }>({})

  const handleSubmit = () => {
    const errs: typeof errors = {}
    if (!missionName.trim()) errs.missionName = 'Nama misi wajib diisi'
    if (!locationName.trim()) errs.locationName = 'Lokasi wajib diisi'
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    onSave(missionName.trim(), locationName.trim())
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-1">Simpan Misi</h2>
        <p className="text-xs text-gray-400 mb-4">Stream selesai. Beri nama misi ini untuk disimpan.</p>
        <div className="flex items-center gap-3 mb-5 px-3 py-2.5 bg-gray-50 rounded-xl text-xs text-gray-500">
          <span className="text-base">⏱</span>
          Durasi: <strong className="text-gray-700 font-mono">{duration}</strong>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1.5 block">
              Nama Misi <span className="text-red-500">*</span>
            </label>
            <input
              value={missionName}
              onChange={e => { setMissionName(e.target.value); if (errors.missionName) setErrors(p => ({ ...p, missionName: undefined })) }}
              placeholder="Contoh: Survei Zona B — Pagi"
              autoFocus
              className={`w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none transition-colors ${errors.missionName ? 'border-red-300 bg-red-50' : 'border-gray-200 focus:border-blue-400'}`}
            />
            {errors.missionName && <p className="text-xs text-red-500 mt-1">{errors.missionName}</p>}
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1.5 block">
              Lokasi <span className="text-red-500">*</span>
            </label>
            <input
              value={locationName}
              onChange={e => { setLocationName(e.target.value); if (errors.locationName) setErrors(p => ({ ...p, locationName: undefined })) }}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder="Contoh: Zona B"
              className={`w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none transition-colors ${errors.locationName ? 'border-red-300 bg-red-50' : 'border-gray-200 focus:border-blue-400'}`}
            />
            {errors.locationName && <p className="text-xs text-red-500 mt-1">{errors.locationName}</p>}
          </div>
        </div>
        <button
          onClick={handleSubmit}
          disabled={isSaving}
          className="w-full mt-5 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-2"
        >
          {isSaving
            ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Menyimpan...</>
            : 'Simpan Misi'}
        </button>
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function StreamComponent() {
  const remoteVideoRef = useRef<HTMLVideoElement>(null)
  const localVideoRef = useRef<HTMLVideoElement>(null)
  const websocketRef = useRef<WebSocket | null>(null)
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const localStreamRef = useRef<MediaStream | null>(null)
  const perfIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const speciesIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null)

  const [isClient, setIsClient] = useState(false)
  // 32 hex acak (128-bit). getRandomValues, bukan randomUUID: randomUUID tidak
  // tersedia di HTTP LAN (hanya HTTPS/localhost). Backend wajib [A-Za-z0-9_-]{8,64}.
  const [clientId] = useState(() =>
    Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')
  )
  const [connStatus, setConnStatus] = useState<ConnStatus>('disconnected')
  const [isStreaming, setIsStreaming] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const isRecordingRef = useRef(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [showMissionSaveDialog, setShowMissionSaveDialog] = useState(false)
  const [isSavingMission, setIsSavingMission] = useState(false)

  // Stream controls — semua jadi dropdown, disabled saat streaming
  const [source, setSource] = useState<SourceMode>('server')
  const [profile, setProfile] = useState<Profile>('balanced')
  const [codec, setCodec] = useState<Codec>('h264')
  const [bitrateKbps, setBitrateKbps] = useState(3500)

  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null)
  const [speciesCounts, setSpeciesCounts] = useState<SpeciesCount[]>([])
  const [detectionLogs, setDetectionLogs] = useState<DetectionLog[]>([])
  const [logs, setLogs] = useState<string[]>([])
  const [perfData, setPerfData] = useState<PerformanceData | null>(null)
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)

  const liveSessionId = isStreaming ? activeSession?.id : undefined
  const { data: telemetryData } = useSWR(liveSessionId ? `/api/telemetry/latest?session_id=${liveSessionId}` : null, apiClient.swrFetcher, { refreshInterval: 2000 })
  const { data: auvData } = useSWR(liveSessionId ? `/api/auv-status/latest?session_id=${liveSessionId}` : null, apiClient.swrFetcher, { refreshInterval: 2000 })

  const telemetry = (telemetryData as any)?.data
  const auv = (auvData as any)?.data
  const ph = telemetry?.phLevel ?? 0
  const tds = telemetry?.tdsValue ?? 0
  const doVal = telemetry?.dissolvedOxygen ?? 0
  const temp = telemetry?.waterTemp ?? 0

  const addLog = useCallback((msg: string) => {
    const t = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLogs(prev => [`[${t}] ${msg}`, ...prev.slice(0, 49)])
  }, [])

  useEffect(() => { setIsClient(true) }, [])

  const fetchActiveSession = useCallback(async () => {
    try {
      const data = await apiClient.get<any>('/api/sessions/active')
      if (data?.data) setActiveSession(data.data)
    } catch { setActiveSession(null) }
  }, [])

  const fetchModelInfo = useCallback(async () => {
    try {
      const data = await apiClient.get<ModelInfo>('/api/model-info')
      setModelInfo(data)
      addLog(`Model loaded: ${data.model_loaded ? 'Yes' : 'No'}`)
      if (data.device) addLog(`Device: ${data.device}`)
    } catch { addLog('Failed to fetch model info') }
  }, [addLog])

  useEffect(() => {
    if (!isClient) return
    fetchActiveSession()
    fetchModelInfo()
  }, [isClient, fetchActiveSession, fetchModelInfo])

  // Sync isRecordingRef agar handler WebSocket bisa baca nilai terbaru
  useEffect(() => { isRecordingRef.current = isRecording }, [isRecording])

  // Recording timer
  useEffect(() => {
    if (isRecording) {
      recordingTimerRef.current = setInterval(() => setRecordingSeconds(s => s + 1), 1000)
    } else {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current)
    }
    return () => { if (recordingTimerRef.current) clearInterval(recordingTimerRef.current) }
  }, [isRecording])

  // Species polling
  useEffect(() => {
    if (!isClient || !isStreaming || !activeSession) {
      if (speciesIntervalRef.current) clearInterval(speciesIntervalRef.current)
      return
    }
    const poll = async () => {
      try {
        const [fishData, detData] = await Promise.all([
          apiClient.get<any>(`/api/fish-counts/session/${activeSession.id}`),
          apiClient.get<any>(`/api/detections?session_id=${activeSession.id}&limit=20`),
        ])
        if (fishData?.data?.counts) setSpeciesCounts(fishData.data.counts)
        if (Array.isArray(detData?.data)) {
          setDetectionLogs(detData.data.map((d: any) => ({
            time: new Date(d.detectedAt).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            species: d.speciesName,
            confidence: d.confidence,
            frame: d.frameNumber ?? 0,
          })))
        }
      } catch {}
    }
    poll()
    speciesIntervalRef.current = setInterval(poll, 5000)
    return () => { if (speciesIntervalRef.current) clearInterval(speciesIntervalRef.current) }
  }, [isStreaming, activeSession, isClient])

  // Performance polling
  useEffect(() => {
    if (!isStreaming) { if (perfIntervalRef.current) clearInterval(perfIntervalRef.current); return }
    const poll = async () => {
      try { setPerfData(await apiClient.get<PerformanceData>('/api/performance')) } catch {}
    }
    perfIntervalRef.current = setInterval(poll, 3000)
    return () => { if (perfIntervalRef.current) clearInterval(perfIntervalRef.current) }
  }, [isStreaming])

  const initWebRTC = useCallback(async () => {
    try {
      addLog('Init WebRTC...')
      const ws = new WebSocket(`${API_WS_URL}/ws/${clientId}`)
      websocketRef.current = ws
      ws.onopen = () => { setConnStatus('connected'); addLog('WebSocket connected') }
      ws.onerror = async () => {
        setConnStatus('error')
        addLog('WebSocket error')
        if (isRecordingRef.current) {
          addLog('Menghentikan recording karena koneksi error...')
          try { await apiClient.post(`/api/recording/stop/${clientId}`) } catch {}
          setIsRecording(false)
          setRecordingSeconds(0)
          setIsStreaming(false)
          toast.error('Koneksi WebSocket error. Recording dihentikan otomatis di backend.')
        }
      }
      ws.onclose = async ev => {
        setConnStatus('disconnected')
        addLog(`WebSocket closed: ${ev.code}`)
        if (isRecordingRef.current) {
          addLog('Menghentikan recording karena koneksi terputus...')
          try { await apiClient.post(`/api/recording/stop/${clientId}`) } catch {}
          setIsRecording(false)
          setRecordingSeconds(0)
          setIsStreaming(false)
          toast.error('Koneksi terputus. Recording dihentikan otomatis di backend.')
        }
      }
      ws.onmessage = async ev => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'error') {
            addLog(`Backend error: ${msg.message}`)
            toast.error(msg.message)
          } else {
            await handleWsMessage(msg)
          }
        } catch (err) {
          addLog(`WS message error: ${err instanceof Error ? err.message : String(err)}`)
        }
      }

      const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }], iceCandidatePoolSize: 10 })
      peerConnectionRef.current = pc
      pc.ontrack = ev => {
        if (remoteVideoRef.current && ev.streams[0]) remoteVideoRef.current.srcObject = ev.streams[0]
        addLog('Remote track received')
      }
      pc.onicecandidate = ev => {
        if (ev.candidate && ws.readyState === WebSocket.OPEN)
          ws.send(JSON.stringify({ type: 'ice-candidate', candidate: ev.candidate }))
      }
      pc.onconnectionstatechange = () => addLog(`RTC: ${pc.connectionState}`)
      addLog('WebRTC ready')
    } catch (err) { setConnStatus('error'); addLog(`Init WebRTC failed: ${err instanceof Error ? err.message : String(err)}`) }
  }, [clientId, addLog])

  useEffect(() => {
    if (!isClient) return
    initWebRTC()
    return () => { cleanupStream() }
  }, [isClient])

  const handleWsMessage = async (msg: any) => {
    const pc = peerConnectionRef.current
    if (!pc) return
    if (msg.type === 'answer') {
      await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: msg.sdp }))
      addLog('Answer received')
    } else if (msg.type === 'ice-candidate' && msg.candidate) {
      await pc.addIceCandidate(new RTCIceCandidate(msg.candidate))
    }
  }

  const startStream = async () => {
    const autoLabel = `Sesi — ${new Date().toLocaleString('id-ID', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}`

    // Buat session dengan nama sementara, user isi detail di akhir
    let session = activeSession
    if (!session) {
      try {
        const sessionRes = await apiClient.post<any>('/api/sessions', { locationName: autoLabel })
        if (sessionRes?.data) {
          session = sessionRes.data
          setActiveSession(sessionRes.data)
          addLog(`Session dibuat: ...${sessionRes.data.id.slice(-6)}`)
        }
      } catch (e: any) {
        const msg: string = e?.message || ''
        if (msg.includes('Sudah ada sesi aktif')) {
          try {
            const activeData = await apiClient.get<any>('/api/sessions/active')
            if (activeData?.data) {
              session = activeData.data
              setActiveSession(activeData.data)
              addLog(`Menggunakan sesi aktif: ...${activeData.data.id.slice(-6)}`)
            }
          } catch {
            toast.error('Gagal mengambil sesi aktif. Coba lagi.')
            return
          }
        } else {
          addLog(`Gagal membuat sesi: ${msg}`)
          toast.error('Gagal membuat sesi monitoring. Coba lagi.')
          return
        }
      }
    }

    handleStartStream(session)
  }

  const handleStartStream = async (session: ActiveSession | null) => {

    // Mulai WebRTC setelah sesi siap
    try {
      const pc = peerConnectionRef.current
      if (!pc) return
      addLog(`Start stream — source=${source}, codec=${codec}, profile=${profile}, bitrate=${bitrateKbps}kbps`)
      if (source === 'server') {
        pc.addTransceiver('video', { direction: 'recvonly' })
      } else {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false })
        localStreamRef.current = stream
        if (localVideoRef.current) localVideoRef.current.srcObject = stream
        stream.getTracks().forEach(t => pc.addTrack(t, stream))
      }
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      const ws = websocketRef.current
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'offer', sdp: offer.sdp, profile, codec, maxBitrateKbps: bitrateKbps }))
        addLog('Offer sent')
        setIsStreaming(true)

        // Auto-start recording — tunggu sebentar agar WebRTC sempat handshake
        setTimeout(async () => {
          try {
            const recData = await apiClient.post<any>(`/api/recording/start/${clientId}`)
            if (recData.success) {
              setIsRecording(true)
              addLog('Recording dimulai otomatis')
            } else {
              addLog(`Auto-start recording gagal: ${recData.error}`)
            }
          } catch {
            addLog('Auto-start recording gagal — stream tetap berjalan')
          }
        }, 1500)
      } else {
        addLog('Stream start failed: WebSocket belum siap')
        toast.error('Koneksi belum siap. Tunggu hingga status Connected lalu coba lagi.')
      }
    } catch (e: any) {
      addLog(`Start failed: ${e?.message}`)
      toast.error(`Gagal memulai stream: ${e?.message}`)
    }
  }

  const cleanupStream = () => {
    // Null-kan semua event handler sebelum close agar event lama (onclose/onerror)
    // tidak menimpa status koneksi WebSocket yang baru
    if (websocketRef.current) {
      websocketRef.current.onopen = null
      websocketRef.current.onerror = null
      websocketRef.current.onclose = null
      websocketRef.current.onmessage = null
      websocketRef.current.close()
      websocketRef.current = null
    }
    if (peerConnectionRef.current) {
      peerConnectionRef.current.ontrack = null
      peerConnectionRef.current.onicecandidate = null
      peerConnectionRef.current.onconnectionstatechange = null
      peerConnectionRef.current.close()
      peerConnectionRef.current = null
    }
    localStreamRef.current?.getTracks().forEach(t => t.stop())
    localStreamRef.current = null
    if (localVideoRef.current) localVideoRef.current.srcObject = null
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null
    if (perfIntervalRef.current) clearInterval(perfIntervalRef.current)
  }

  const stopStream = async () => {
    addLog('Stopping stream...')

    if (isRecording) {
      try { await apiClient.post(`/api/recording/stop/${clientId}`) } catch {}
      setIsRecording(false)
    }

    cleanupStream()
    setIsStreaming(false)
    setConnStatus('disconnected')
    setPerfData(null)

    if (activeSession) {
      setShowMissionSaveDialog(true)
    } else {
      setRecordingSeconds(0)
      setSpeciesCounts([])
      setDetectionLogs([])
      addLog('Stream stopped')
      setTimeout(() => { initWebRTC(); fetchActiveSession() }, 300)
    }
  }

  const handleSaveMission = async (missionName: string, locationName: string) => {
    if (!activeSession) return
    setIsSavingMission(true)
    try {
      await apiClient.patch(`/api/sessions/${activeSession.id}`, {
        status: 'Completed',
        locationName: `${missionName} — ${locationName}`,
      })
      toast.success(`Misi "${missionName}" berhasil disimpan.`)
      addLog(`Misi disimpan: ${missionName} — ${locationName}`)
    } catch {
      toast.error('Gagal menyimpan misi. Coba lagi.')
    } finally {
      setIsSavingMission(false)
      setShowMissionSaveDialog(false)
      setActiveSession(null)
      setSpeciesCounts([])
      setDetectionLogs([])
      setRecordingSeconds(0)
      addLog('Stream stopped')
      setTimeout(() => { initWebRTC(); fetchActiveSession() }, 300)
    }
  }

  const stopRecordingOnly = async () => {
    try { await apiClient.post(`/api/recording/stop/${clientId}`) } catch {}
    setIsRecording(false)
    setRecordingSeconds(0)
    addLog('Recording stopped — stream still running')
  }

  const totalFish = speciesCounts.reduce((s, c) => s + c.totalCount, 0)
  const missionStartAgo = activeSession
    ? Math.floor((Date.now() - new Date(activeSession.startTime).getTime()) / 60000)
    : 0

  const connStatusStyle = connStatus === 'connected' ? 'text-green-600' : connStatus === 'error' ? 'text-red-500' : 'text-gray-400'
  const connDotStyle = connStatus === 'connected' ? 'bg-green-500 animate-pulse' : connStatus === 'error' ? 'bg-red-500' : 'bg-gray-300'

  if (!isClient) return null

  return (
    <div className="min-h-screen bg-gray-50">
      <Header title="Live Stream" subtitle="Live Stream — Command Center" emoji="🎥" />

      {showMissionSaveDialog && activeSession && (
        <MissionSaveDialog
          duration={formatDuration(recordingSeconds)}
          onSave={handleSaveMission}
          isSaving={isSavingMission}
        />
      )}

      <div className="px-6 py-4 space-y-4">

        {/* ── Status Bar ── */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">

            {/* Left: status + dropdown controls */}
            <div className="flex flex-wrap items-center gap-3">
              {/* Connection status */}
              <span className={`flex items-center gap-1.5 text-sm font-medium ${connStatusStyle}`}>
                <span className={`w-2 h-2 rounded-full ${connDotStyle}`} />
                Status: {connStatus === 'connected' ? 'Connected' : connStatus === 'error' ? 'Error' : 'Disconnected'}
              </span>

              <span className="w-px h-4 bg-gray-200" />

              {/* Source dropdown */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400">Source:</span>
                <select
                  value={source}
                  onChange={e => setSource(e.target.value as SourceMode)}
                  disabled={isStreaming}
                  className={selectCls(isStreaming)}
                >
                  <option value="server">Server RTSP</option>
                  <option value="device">Device Cam</option>
                </select>
              </div>

              {/* Profile dropdown */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400">Profile:</span>
                <select
                  value={profile}
                  onChange={e => setProfile(e.target.value as Profile)}
                  disabled={isStreaming}
                  className={selectCls(isStreaming)}
                >
                  <option value="balanced">Balanced (TCP)</option>
                  <option value="ultra">Ultra-Low (UDP)</option>
                </select>
              </div>

              {/* Codec dropdown */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400">Codec:</span>
                <select
                  value={codec}
                  onChange={e => setCodec(e.target.value as Codec)}
                  disabled={isStreaming}
                  className={selectCls(isStreaming)}
                >
                  <option value="h264">H.264</option>
                  <option value="vp8">VP8</option>
                </select>
              </div>

              {/* Bitrate input */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400">Bitrate:</span>
                <div className={`flex items-center border rounded-lg overflow-hidden text-xs ${isStreaming ? 'opacity-50' : 'border-gray-200'}`}>
                  <input
                    type="number"
                    min={500}
                    max={12000}
                    step={100}
                    value={bitrateKbps}
                    onChange={e => setBitrateKbps(Number(e.target.value))}
                    disabled={isStreaming}
                    className="w-16 px-2 py-1.5 text-gray-700 bg-white border-none outline-none text-center disabled:cursor-not-allowed"
                  />
                  <span className="px-2 py-1.5 bg-gray-50 text-gray-400 border-l border-gray-200">kbps</span>
                </div>
              </div>
            </div>

            {/* Right: action buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => { cleanupStream(); setTimeout(initWebRTC, 300) }}
                disabled={isStreaming}
                className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Refresh
              </button>

              {!isStreaming ? (
                <button
                  onClick={startStream}
                  disabled={connStatus !== 'connected'}
                  className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:text-gray-400 text-white rounded-lg font-medium transition-colors"
                >
                  Start Stream
                </button>
              ) : (
                <button
                  onClick={stopStream}
                  className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
                >
                  Stop
                </button>
              )}

              {/* REC indicator — auto-start, hanya tampil status */}
              {isStreaming && (
                <span className={`px-3 py-2 text-sm rounded-lg font-medium flex items-center gap-2 ${
                  isRecording
                    ? 'bg-red-600 text-white'
                    : 'bg-gray-100 text-gray-400'
                }`}>
                  <span className={`w-2.5 h-2.5 rounded-full ${isRecording ? 'bg-white animate-pulse' : 'bg-gray-300'}`} />
                  {isRecording ? `REC ${formatDuration(recordingSeconds)}` : 'REC Starting...'}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ── Video Grid ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Preview */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">
                {source === 'server' ? 'Preview (MediaMTX)' : 'Input Preview (Device Cam)'}
              </h3>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${isStreaming ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-400'}`}>
                {isStreaming ? '● LIVE' : '● OFF'}
              </span>
            </div>
            <div className="relative bg-gray-900" style={{ aspectRatio: '16/9' }}>
              {source === 'server' && isStreaming ? (
                <iframe src={IFRAME_PREVIEW_URL} className="w-full h-full" allow="autoplay; encrypted-media" allowFullScreen />
              ) : source === 'device' ? (
                <video ref={localVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <span className="text-gray-600 text-sm">Stream tidak aktif</span>
                </div>
              )}
              {isStreaming && auv && (
                <div className="absolute top-2 left-2 flex gap-2">
                  <span className="bg-black/60 text-white text-xs px-2 py-1 rounded-lg">DEPTH {auv.depth?.toFixed(1)}m</span>
                  <span className="bg-black/60 text-white text-xs px-2 py-1 rounded-lg">SIGNAL Strong</span>
                  {isRecording && (
                    <span className="bg-red-600/80 text-white text-xs px-2 py-1 rounded-lg font-mono animate-pulse">
                      REC {formatDuration(recordingSeconds)}
                    </span>
                  )}
                </div>
              )}
            </div>
            <div className="px-4 py-2 text-xs text-gray-400">
              Preview: {IFRAME_PREVIEW_URL} · 1920x1080 · 30 FPS
            </div>
          </div>

          {/* YOLO Detection */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">
                YOLO Detection (WebRTC) — {modelInfo?.device ?? 'Jetson Orin'}
              </h3>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                isStreaming && modelInfo?.model_loaded ? 'bg-green-100 text-green-600'
                : modelInfo?.model_loaded ? 'bg-blue-100 text-blue-600'
                : 'bg-gray-100 text-gray-400'
              }`}>
                {isStreaming && modelInfo?.model_loaded ? 'AI ACTIVE'
                  : modelInfo?.model_loaded ? 'AI Ready'
                  : 'AI Off'}
              </span>
            </div>
            <div className="relative bg-gray-900" style={{ aspectRatio: '16/9' }}>
              <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
              {!isStreaming && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                  <span className="text-gray-500 text-sm font-medium">YOLO — No Stream</span>
                  <span className="text-gray-600 text-xs">Butuh ROV + RTSP feed aktif</span>
                </div>
              )}
              {isStreaming && perfData && (
                <div className="absolute top-2 left-2 flex gap-2">
                  <span className="bg-black/60 text-white text-xs px-2 py-1 rounded-lg">DETECTIONS {totalFish}</span>
                  <span className="bg-black/60 text-white text-xs px-2 py-1 rounded-lg">FPS {(perfData.fps ?? 0).toFixed(0)}</span>
                  <span className="bg-black/60 text-white text-xs px-2 py-1 rounded-lg">MODEL {modelInfo?.device ?? 'YOLOv8'}</span>
                  <span className="bg-black/60 text-white text-xs px-2 py-1 rounded-lg">CONF THRESH 0.65</span>
                </div>
              )}
            </div>
            <div className="px-4 py-2 text-xs text-gray-400">
              Model: YOLOv8-fish · Device: {modelInfo?.device ?? 'Jetson Orin NX'} · Inference: {perfData?.inference_fps ? `${(1000 / perfData.inference_fps).toFixed(0)}ms` : '41ms'}/frame
            </div>
          </div>
        </div>

        {/* ── Water Quality ── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'pH Air', value: ph, unit: 'pH', range: 'Normal range: 6.5 – 8.5', max: 14, status: getPhStatus(ph) },
            { label: 'TDS (Total Dissolved Solids)', value: tds, unit: 'ppm', range: 'Normal range: 100 – 300 ppm', max: 1000, status: getTdsStatus(tds) },
            { label: 'DO (Dissolved Oxygen)', value: doVal, unit: 'mg/L', range: 'Normal range: 6.0 – 8.0 mg/L', max: 15, status: getDoStatus(doVal) },
            { label: 'Suhu Air', value: temp, unit: 'C', range: 'Normal range: 26 – 30 C', max: 50, status: getTempStatus(temp) },
          ].map(({ label, value, unit, range, max, status }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-4">
              <p className="text-xs text-gray-400 mb-1">{label}</p>
              <div className="flex items-baseline gap-1 mb-1">
                <span className="text-2xl font-bold text-gray-800">{value.toFixed(1)}</span>
                <span className="text-xs text-gray-400">{unit}</span>
              </div>
              <p className="text-xs text-gray-400 mb-2">{range}</p>
              <span className={`text-xs font-medium flex items-center gap-1 mb-2 ${status.color}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />{status.label}
              </span>
              <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className={`h-full rounded-full ${status.bar} transition-all duration-500`} style={{ width: `${progressPct(value, max)}%` }} />
              </div>
            </div>
          ))}
        </div>

        {/* ── Species Counter + System Logs ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

          {/* AI Species Counter */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">AI Species Counter & Detection Log</h3>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${isStreaming ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-400'}`}>
                {isStreaming ? '● LIVE' : '● OFF'}
              </span>
            </div>
            <div className="p-4">
              {/* Dark summary panel */}
              <div className="bg-gray-900 rounded-xl p-4 mb-4 text-white">
                <p className="text-xs text-gray-400 mb-1">Total Ikan terdeteksi (sesi ini)</p>
                <p className="text-4xl font-bold mb-1">{totalFish}</p>
                {activeSession && <p className="text-xs text-gray-400">Sejak misi dimulai {missionStartAgo} menit lalu</p>}
                <div className="mt-3 space-y-1.5">
                  {(speciesCounts.length > 0
                    ? speciesCounts
                    : ['Kerapu', 'Bandeng', 'Teri', 'Lainnya / Unknown'].map(n => ({ speciesName: n, totalCount: 0 }))
                  ).map((s, i) => {
                    const name = 'speciesName' in s ? s.speciesName : String(s)
                    const count = 'totalCount' in s ? s.totalCount : 0
                    return (
                      <div key={name} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getSpeciesColor(name, i) }} />
                          <span className="text-gray-300">{name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1 bg-gray-700 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${totalFish > 0 ? (count / totalFish) * 100 : 0}%`, backgroundColor: getSpeciesColor(name, i) }} />
                          </div>
                          <span className="text-gray-300 w-4 text-right">{count}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Detection log table */}
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-100">
                    <th className="text-left pb-2 font-medium">WAKTU</th>
                    <th className="text-left pb-2 font-medium">SPESIES</th>
                    <th className="text-left pb-2 font-medium">CONFIDENCE</th>
                    <th className="text-right pb-2 font-medium">FRAME</th>
                  </tr>
                </thead>
                <tbody>
                  {detectionLogs.length > 0 ? detectionLogs.map((log, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-2 text-gray-500 font-mono">{log.time}</td>
                      <td className="py-2">
                        <span className="px-2 py-0.5 rounded-full text-white text-xs font-medium" style={{ backgroundColor: getSpeciesColor(log.species, i) }}>
                          {log.species}
                        </span>
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${log.confidence * 100}%`, backgroundColor: getSpeciesColor(log.species, i) }} />
                          </div>
                          <span className="text-gray-600">{(log.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="py-2 text-right text-gray-400 font-mono">#{log.frame}</td>
                    </tr>
                  )) : Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-2 text-gray-200 font-mono">—</td>
                      <td className="py-2 text-gray-200">—</td>
                      <td className="py-2 text-gray-200">—</td>
                      <td className="py-2 text-right text-gray-200">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* System Logs */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">System Logs</h3>
              <button onClick={() => setLogs([])} className="text-xs text-gray-400 hover:text-gray-600 transition-colors">Clear</button>
            </div>
            <div className="bg-gray-900 m-4 rounded-xl p-4 h-96 overflow-y-auto">
              <div className="space-y-1 font-mono text-xs">
                {logs.length > 0 ? logs.map((l, i) => (
                  <div key={i} className={
                    l.includes('Detection') ? 'text-orange-400' :
                    l.includes('threshold') || l.includes('di atas') || l.includes('di bawah') ? 'text-red-400' :
                    l.includes('healthy') || l.includes('loaded') ? 'text-blue-400' :
                    'text-green-400'
                  }>{l}</div>
                )) : <div className="text-gray-600">No logs</div>}
              </div>
            </div>
          </div>
        </div>

        {/* ── Catatan ── */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Catatan</h3>
          <ul className="space-y-1.5 text-sm text-gray-500 list-none">
            <li>Panel kiri (Server RTSP) hanya preview via IFRAME. Input deteksi tetap di-pull dari RTSP oleh backend.</li>
            <li>Kontrol Codec / Profile / Bitrate dikirim via signaling. Backend boleh mengabaikan bila belum diimplementasikan.</li>
            <li>Jika ingin benar-benar enforce bitrate/codec dari sisi server, perlu dukungan di backend (mis. setSenderParameters/SDP munging).</li>
          </ul>
        </div>

      </div>
    </div>
  )
}