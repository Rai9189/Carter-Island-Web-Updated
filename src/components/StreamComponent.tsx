'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Header from '@/components/layout/Header'
import { apiClient } from '@/lib/api-client';

interface StreamComponentProps {
  apiUrl?: string;
  userFullName?: string;
}

interface PerformanceData {
  fps?: number;
  inference_fps?: number;
  active_ws?: number;
  active_peer_connections?: number;
  device?: string;
  model_loaded?: boolean;
  cuda_available?: boolean;
}

interface ModelInfo {
  model_loaded: boolean;
  num_classes?: number;
  device?: string;
}

interface ActiveSession {
  id: string;
  locationName: string;
  startTime: string;
  status: string;
}

interface SpeciesCount {
  speciesName: string;
  totalCount: number;
}

const IFRAME_PREVIEW_URL = 'http://192.168.2.2:8889/cam/';
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#FF6B9D'];

type Profile   = 'balanced' | 'ultra';
type Codec     = 'h264' | 'vp8';
type SourceMode = 'server' | 'device';

export default function StreamComponent({
  apiUrl = 'ws://localhost:8000',
  userFullName,
}: StreamComponentProps) {
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const localVideoRef  = useRef<HTMLVideoElement>(null);

  const [isClient, setIsClient]               = useState(false);
  const [clientId, setClientId]               = useState('');
  const [isStreaming, setIsStreaming]         = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connected' | 'error'>('disconnected');
  const [modelInfo, setModelInfo]             = useState<ModelInfo | null>(null);
  const [performanceData, setPerformanceData] = useState<PerformanceData | null>(null);
  const [logs, setLogs]                       = useState<string[]>([]);

  // Recording
  const [isRecording, setIsRecording]   = useState(false);
  const [recordingId, setRecordingId]   = useState<string | null>(null);

  // Session
  const [activeSession, setActiveSession]         = useState<ActiveSession | null>(null);
  const [sessionLoading, setSessionLoading]       = useState(false);
  const [newLocationName, setNewLocationName]     = useState('');
  const [showSessionForm, setShowSessionForm]     = useState(false);

  // Species counter
  const [speciesCounts, setSpeciesCounts]         = useState<SpeciesCount[]>([]);
  const speciesIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // UI controls
  const [source, setSource]           = useState<SourceMode>('server');
  const [profile, setProfile]         = useState<Profile>('balanced');
  const [codec, setCodec]             = useState<Codec>('h264');
  const [bitrateKbps, setBitrateKbps] = useState<number>(3500);
  const [targetFps, setTargetFps]     = useState<number>(30);

  // RTC & WS
  const websocketRef      = useRef<WebSocket | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef    = useRef<MediaStream | null>(null);
  const perfIntervalRef   = useRef<NodeJS.Timeout | null>(null);

  const httpUrl = apiUrl.replace('ws://', 'http://').replace('wss://', 'https://');

  const addLog = useCallback((msg: string) => {
    const t = new Date().toLocaleTimeString();
    setLogs(prev => [`[${t}] ${msg}`, ...prev.slice(0, 99)]);
  }, []);

  useEffect(() => {
    setIsClient(true);
    setClientId(Math.random().toString(36).substring(7));
  }, []);

  // ── Cek sesi aktif saat mount ──
  useEffect(() => {
    if (!isClient) return;
    fetchActiveSession();
  }, [isClient]);

  const fetchActiveSession = async () => {
    try {
      const data = await apiClient.get('/api/sessions/active');
      if (data?.data) {
        setActiveSession(data.data);
        addLog(`Sesi aktif ditemukan: ${data.data.locationName}`);
      }
    } catch {
      setActiveSession(null);
    }
  };

  // ── Start sesi baru ──
  const handleStartSession = async () => {
    if (!newLocationName.trim()) return;
    setSessionLoading(true);
    try {
      const data = await apiClient.post('/api/sessions', {
        locationName: newLocationName.trim(),
      });
      if (data?.data) {
        setActiveSession(data.data);
        setNewLocationName('');
        setShowSessionForm(false);
        setSpeciesCounts([]);
        addLog(`Sesi dimulai: ${data.data.locationName} (${data.data.id.substring(0, 8)}...)`);
      }
    } catch (e: any) {
      addLog(`Gagal memulai sesi: ${e?.message || 'Error'}`);
    } finally {
      setSessionLoading(false);
    }
  };

  // ── Selesaikan sesi ──
  const handleCompleteSession = async () => {
    if (!activeSession) return;
    if (!confirm(`Selesaikan sesi "${activeSession.locationName}"?`)) return;
    setSessionLoading(true);
    try {
      await apiClient.patch(`/api/sessions/${activeSession.id}`, {
        status: 'Completed',
      });
      setActiveSession(null);
      setSpeciesCounts([]);
      addLog('Sesi diselesaikan');
    } catch (e: any) {
      addLog(`Gagal menyelesaikan sesi: ${e?.message || 'Error'}`);
    } finally {
      setSessionLoading(false);
    }
  };

  // ── Polling species counter selama streaming + ada sesi ──
  useEffect(() => {
    if (!isClient) return;

    const pollSpecies = async () => {
      if (!activeSession) return;
      try {
        const data = await apiClient.get(
          `/api/fish-counts/session/${activeSession.id}`
        );
        if (data?.data?.counts) {
          setSpeciesCounts(data.data.counts);
        }
      } catch {
        // ignore
      }
    };

    if (isStreaming && activeSession) {
      speciesIntervalRef.current = setInterval(pollSpecies, 5000);
      pollSpecies(); // langsung poll pertama kali
    } else {
      if (speciesIntervalRef.current) {
        clearInterval(speciesIntervalRef.current);
        speciesIntervalRef.current = null;
      }
    }

    return () => {
      if (speciesIntervalRef.current) clearInterval(speciesIntervalRef.current);
    };
  }, [isStreaming, activeSession, isClient]);

  // ── Model info ──
  useEffect(() => {
    if (!isClient) return;
    const fetchModelInfo = async () => {
      try {
        const res  = await fetch(`${httpUrl}/api/model-info`);
        const data = await res.json();
        setModelInfo(data);
        addLog(`Model loaded: ${data.model_loaded ? 'Yes' : 'No'}`);
        if (data.device) addLog(`Device: ${data.device}`);
      } catch {
        addLog('Failed to fetch model info');
      }
    };
    fetchModelInfo();
  }, [apiUrl, addLog, isClient]);

  // ── Performance polling ──
  useEffect(() => {
    if (!isClient) return;
    const poll = async () => {
      try {
        const res  = await fetch(`${httpUrl}/api/performance`);
        const data = await res.json();
        setPerformanceData(data);
      } catch {}
    };
    if (isStreaming) {
      perfIntervalRef.current = setInterval(poll, 1000);
    } else if (perfIntervalRef.current) {
      clearInterval(perfIntervalRef.current);
      perfIntervalRef.current = null;
    }
    return () => {
      if (perfIntervalRef.current) clearInterval(perfIntervalRef.current);
    };
  }, [apiUrl, isStreaming, isClient]);

  // ── WebRTC ──
  const initializeWebRTC = async () => {
    if (!isClient || !clientId) return;
    try {
      setConnectionStatus('disconnected');
      addLog('Init WebRTC...');

      websocketRef.current = new WebSocket(`${apiUrl}/ws/${clientId}`);
      websocketRef.current.onopen  = () => { setConnectionStatus('connected'); addLog('WebSocket connected'); };
      websocketRef.current.onmessage = async (event) => {
        try { await handleMessage(JSON.parse(event.data)); } catch { addLog('WS message parse error'); }
      };
      websocketRef.current.onerror = () => { setConnectionStatus('error'); addLog('WebSocket error'); };
      websocketRef.current.onclose = (ev) => { setConnectionStatus('disconnected'); addLog(`WebSocket closed: ${ev.code}`); };

      peerConnectionRef.current = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
        ],
        iceCandidatePoolSize: 10,
      });

      peerConnectionRef.current.ontrack = (ev) => {
        if (remoteVideoRef.current && ev.streams[0]) remoteVideoRef.current.srcObject = ev.streams[0];
        addLog('Remote track received');
      };
      peerConnectionRef.current.onicecandidate = (ev) => {
        if (ev.candidate && websocketRef.current)
          websocketRef.current.send(JSON.stringify({ type: 'ice-candidate', candidate: ev.candidate }));
      };
      peerConnectionRef.current.onconnectionstatechange = () =>
        addLog(`RTC state: ${peerConnectionRef.current?.connectionState}`);
    } catch {
      setConnectionStatus('error');
      addLog('Init WebRTC failed');
    }
  };

  const applyCodecPreference = (transceiver: RTCRtpTransceiver, wanted: Codec) => {
    try {
      const rxCaps = (window as any).RTCRtpReceiver?.getCapabilities?.('video');
      const txCaps = (window as any).RTCRtpSender?.getCapabilities?.('video');
      const caps   = rxCaps || txCaps;
      if (!caps?.codecs?.length) return;
      const isH264   = wanted === 'h264';
      const primary  = caps.codecs.filter((c: any) => c.mimeType?.toLowerCase().includes(isH264 ? 'h264' : 'vp8'));
      const secondary = caps.codecs.filter((c: any) => !c.mimeType?.toLowerCase().includes(isH264 ? 'h264' : 'vp8'));
      const prefs    = [...primary, ...secondary];
      if ((transceiver as any).setCodecPreferences && prefs.length) {
        (transceiver as any).setCodecPreferences(prefs);
        addLog(`Codec preference set: ${wanted.toUpperCase()}`);
      }
    } catch {}
  };

  const startServerStream = async () => {
    addLog(`Start SERVER (codec=${codec}, profile=${profile}, bitrate=${bitrateKbps} kbps)`);
    const pc = peerConnectionRef.current;
    if (!pc) throw new Error('RTCPeerConnection not ready');
    const trx = pc.addTransceiver('video', { direction: 'recvonly' });
    applyCodecPreference(trx, codec);
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({ type: 'offer', sdp: offer.sdp, profile, codec, maxBitrateKbps: bitrateKbps, targetFps }));
      addLog('Offer (server) sent');
    } else throw new Error('WebSocket not connected');
  };

  const startDeviceStream = async () => {
    addLog(`Start DEVICE (codec=${codec}, bitrate=${bitrateKbps} kbps)`);
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: targetFps }, facingMode: 'environment' },
      audio: false,
    });
    localStreamRef.current = stream;
    if (localVideoRef.current) localVideoRef.current.srcObject = stream;
    const pc = peerConnectionRef.current;
    if (!pc) throw new Error('RTCPeerConnection not ready');
    stream.getTracks().forEach(t => pc.addTrack(t, stream));
    const offer = await pc.createOffer({ offerToReceiveVideo: true, offerToReceiveAudio: false });
    await pc.setLocalDescription(offer);
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({ type: 'offer', sdp: offer.sdp, profile, codec, maxBitrateKbps: bitrateKbps, targetFps }));
      addLog('Offer (device) sent');
    } else throw new Error('WebSocket not connected');
  };

  const startStream = async () => {
    try {
      if (source === 'server') await startServerStream();
      else await startDeviceStream();
      setIsStreaming(true);
      addLog('Stream started');
    } catch (e: any) { addLog(`Start failed: ${e?.message || String(e)}`); }
  };

  const stopStream = () => {
    try {
      addLog('Stopping...');
      if (isRecording) stopRecording();
      localStreamRef.current?.getTracks().forEach(t => t.stop());
      localStreamRef.current = null;
      if (localVideoRef.current) localVideoRef.current.srcObject = null;
      if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
      peerConnectionRef.current?.getSenders().forEach(s => { try { s.track?.stop(); } catch {} });
      peerConnectionRef.current?.close();
      peerConnectionRef.current = null;
      websocketRef.current?.close();
      websocketRef.current = null;
      if (perfIntervalRef.current) { clearInterval(perfIntervalRef.current); perfIntervalRef.current = null; }
      setIsStreaming(false);
      setConnectionStatus('disconnected');
      setPerformanceData(null);
      addLog('Stopped');
    } catch { addLog('Stop error'); }
  };

  const startRecording = async () => {
    if (!isStreaming || !clientId) { addLog('Cannot start recording: Not streaming'); return; }
    try {
      const response = await fetch(`${httpUrl}/api/recording/start/${clientId}`, { method: 'POST' });
      const data = await response.json();
      if (data.success) { setIsRecording(true); setRecordingId(data.recording_id); addLog(`Recording started: ${data.recording_id}`); }
      else addLog(`Failed to start recording: ${data.error}`);
    } catch (e: any) { addLog(`Recording error: ${e?.message || String(e)}`); }
  };

  const stopRecording = async () => {
    if (!isRecording || !clientId) return;
    try {
      const response = await fetch(`${httpUrl}/api/recording/stop/${clientId}`, { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        setIsRecording(false);
        addLog(`Recording stopped: ${(data.recording?.duration || 0).toFixed(1)}s, ${((data.recording?.file_size || 0)/1024/1024).toFixed(2)}MB`);
        setRecordingId(null);
      } else addLog(`Failed to stop recording: ${data.error}`);
    } catch (e: any) { addLog(`Stop recording error: ${e?.message || String(e)}`); setIsRecording(false); setRecordingId(null); }
  };

  const handleMessage = async (msg: any) => {
    const pc = peerConnectionRef.current;
    if (!pc) return;
    try {
      if (msg.type === 'answer') { await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: msg.sdp })); addLog('Answer set'); }
      else if (msg.type === 'ice-candidate' && msg.candidate) await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
    } catch { addLog('Process WS message failed'); }
  };

  useEffect(() => {
    if (isClient && clientId) {
      initializeWebRTC();
      return () => { stopStream(); };
    }
  }, [isClient, clientId]);

  const getStatusColor = (s: string) =>
    s === 'connected' ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : s === 'error'   ? 'bg-red-50 text-red-700 border-red-200'
    : 'bg-slate-50 text-slate-700 border-slate-200';

  const fpsClass = (v: number) => v >= 25 ? 'text-emerald-600' : v >= 15 ? 'text-amber-600' : 'text-red-600';

  const totalFish = speciesCounts.reduce((sum, s) => sum + s.totalCount, 0);

  if (!isClient) return (
    <div className="min-h-screen bg-slate-50 p-6 flex items-center justify-center">
      <p className="text-slate-600">Loading...</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <Header title="Live Stream" subtitle="Live Stream Monitoring 🌊" emoji="" />
      <div className="p-6">
        <div className="max-w-7xl mx-auto space-y-6">

          {/* ── Session Control Bar ── */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className={`w-2.5 h-2.5 rounded-full ${activeSession ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`} />
                <div>
                  <p className="text-sm font-semibold text-slate-800">
                    {activeSession ? `Sesi: ${activeSession.locationName}` : 'Tidak ada sesi aktif'}
                  </p>
                  {activeSession && (
                    <p className="text-xs text-slate-400 font-mono">
                      ID: {activeSession.id.substring(0, 16)}...
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {!activeSession ? (
                  <>
                    {showSessionForm ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={newLocationName}
                          onChange={e => setNewLocationName(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && handleStartSession()}
                          placeholder="Nama lokasi survei..."
                          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-48"
                          autoFocus
                        />
                        <button
                          onClick={handleStartSession}
                          disabled={sessionLoading || !newLocationName.trim()}
                          className="px-4 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium"
                        >
                          {sessionLoading ? 'Memulai...' : 'Mulai'}
                        </button>
                        <button
                          onClick={() => setShowSessionForm(false)}
                          className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-sm"
                        >
                          Batal
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setShowSessionForm(true)}
                        className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium flex items-center gap-1.5"
                      >
                        + Mulai Sesi Misi
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    onClick={handleCompleteSession}
                    disabled={sessionLoading}
                    className="px-4 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium"
                  >
                    {sessionLoading ? 'Memproses...' : 'Selesaikan Sesi'}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* ── Status & Stream Controls ── */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className={`px-4 py-2 rounded-lg border text-sm font-medium flex items-center gap-2 ${getStatusColor(connectionStatus)}`}>
                  <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-emerald-500' : connectionStatus === 'error' ? 'bg-red-500' : 'bg-slate-400'}`} />
                  {connectionStatus === 'error' ? 'websocket error' : connectionStatus}
                </div>
                {performanceData?.device && (
                  <div className="px-3 py-2 bg-slate-50 rounded-lg border border-slate-200 text-sm text-slate-700">
                    Device: {performanceData.device}
                  </div>
                )}
                {performanceData?.cuda_available && (
                  <div className="px-3 py-2 bg-emerald-50 rounded-lg border border-emerald-200 text-sm text-emerald-700">
                    CUDA Enabled
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {/* Source */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-600">Source:</span>
                  <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
                    <button onClick={() => setSource('server')} className={`px-3 py-1.5 text-sm ${source === 'server' ? 'bg-slate-900 text-white' : 'bg-white text-slate-700'}`}>Server RTSP</button>
                    <button onClick={() => setSource('device')} className={`px-3 py-1.5 text-sm ${source === 'device' ? 'bg-slate-900 text-white' : 'bg-white text-slate-700'}`}>Device Cam</button>
                  </div>
                </div>
                {/* Profile */}
                <select value={profile} onChange={e => setProfile(e.target.value as Profile)} className="border border-slate-300 rounded-lg px-2 py-1 text-sm">
                  <option value="balanced">Balanced (TCP)</option>
                  <option value="ultra">Ultra-Low (UDP)</option>
                </select>
                {/* Codec */}
                <select value={codec} onChange={e => setCodec(e.target.value as Codec)} className="border border-slate-300 rounded-lg px-2 py-1 text-sm">
                  <option value="h264">H.264</option>
                  <option value="vp8">VP8</option>
                </select>
                {/* Bitrate */}
                <input type="number" min={500} max={12000} step={100} value={bitrateKbps} onChange={e => setBitrateKbps(Number(e.target.value))}
                  className="w-24 border border-slate-300 rounded-lg px-2 py-1 text-sm" placeholder="Bitrate" />
              </div>

              <div className="flex gap-2">
                <button onClick={() => window.location.reload()} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm">Refresh</button>
                <button onClick={startStream} disabled={isStreaming || connectionStatus !== 'connected'}
                  className="px-5 py-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 text-white rounded-lg font-medium text-sm">
                  {isStreaming ? 'Streaming...' : 'Start Stream'}
                </button>
                <button onClick={stopStream} disabled={!isStreaming}
                  className="px-5 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-400 text-white rounded-lg font-medium text-sm">
                  Stop
                </button>
                {isStreaming && (
                  !isRecording ? (
                    <button onClick={startRecording}
                      className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium text-sm flex items-center gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-white" /> Record
                    </button>
                  ) : (
                    <button onClick={stopRecording}
                      className="px-5 py-2 bg-red-800 hover:bg-red-900 text-white rounded-lg font-medium text-sm flex items-center gap-1.5 animate-pulse">
                      <div className="w-3 h-3 bg-white rounded-sm" /> Stop Rec
                    </button>
                  )
                )}
              </div>
            </div>
          </div>

          {/* ── Video Grid ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Preview */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="border-b border-slate-200 px-4 py-3">
                <h3 className="text-sm font-medium text-slate-900">
                  {source === 'server' ? 'Preview (MediaMTX)' : 'Input Preview (Device)'}
                </h3>
              </div>
              <div className="p-4">
                <div className="relative bg-slate-900 rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
                  {source === 'server' ? (
                    <iframe src={IFRAME_PREVIEW_URL} className="w-full h-full" allow="autoplay; encrypted-media" allowFullScreen />
                  ) : (
                    <video ref={localVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
                  )}
                </div>
                {source === 'server' && <p className="text-xs text-slate-400 mt-2">Preview: {IFRAME_PREVIEW_URL}</p>}
              </div>
            </div>

            {/* YOLO Detection */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="border-b border-slate-200 px-4 py-3 flex items-center justify-between">
                <h3 className="text-sm font-medium text-slate-900">YOLO Detection (WebRTC)</h3>
                {isStreaming && <div className="bg-red-500 text-white px-2 py-0.5 rounded text-xs font-medium">LIVE</div>}
              </div>
              <div className="p-4">
                <div className="relative bg-slate-900 rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
                  <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
                  {!isStreaming && (
                    <div className="absolute inset-0 flex items-center justify-center text-center text-slate-400">
                      <div><div className="text-2xl mb-1">YOLO</div><p className="text-sm">No Stream</p></div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* ── AI Species Counter ── */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="border-b border-slate-200 px-4 py-3 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium text-slate-900">AI Species Counter</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {activeSession
                    ? `Sesi: ${activeSession.locationName} — Update tiap 5 detik`
                    : 'Mulai sesi misi untuk mulai menghitung spesies'}
                </p>
              </div>
              {activeSession && (
                <div className="text-right">
                  <p className="text-2xl font-bold text-blue-600">{totalFish}</p>
                  <p className="text-xs text-slate-400">Total Individu</p>
                </div>
              )}
            </div>
            <div className="p-4">
              {!activeSession ? (
                <div className="text-center py-8 text-slate-400 text-sm">
                  Belum ada sesi aktif. Mulai sesi misi terlebih dahulu.
                </div>
              ) : speciesCounts.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-sm">
                  {isStreaming ? 'Menunggu deteksi...' : 'Mulai streaming untuk mendeteksi ikan'}
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {speciesCounts.map((s, i) => (
                    <div key={s.speciesName} className="p-3 rounded-xl border border-slate-100 bg-slate-50">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        <p className="text-xs font-medium text-slate-600 truncate">{s.speciesName}</p>
                      </div>
                      <p className="text-2xl font-bold text-slate-800">{s.totalCount}</p>
                      <div className="mt-1.5 h-1 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: totalFish > 0 ? `${(s.totalCount / totalFish) * 100}%` : '0%',
                            backgroundColor: COLORS[i % COLORS.length],
                          }}
                        />
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        {totalFish > 0 ? `${((s.totalCount / totalFish) * 100).toFixed(1)}%` : '0%'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── System Logs ── */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="border-b border-slate-200 px-4 py-3">
              <h3 className="text-sm font-medium text-slate-900">System Logs</h3>
            </div>
            <div className="p-4">
              <div className="bg-slate-900 rounded-lg p-4 h-44 overflow-y-auto">
                <div className="space-y-1 text-sm font-mono">
                  {logs.length
                    ? logs.map((l, i) => <div key={i} className="text-emerald-400">{l}</div>)
                    : <div className="text-slate-500">No logs</div>}
                </div>
              </div>
            </div>
          </div>

          {/* ── Performance ── */}
          {performanceData && isStreaming && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h3 className="text-sm font-medium text-slate-900 mb-4">Performance Monitor</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Render FPS',   value: (performanceData.fps ?? 0).toFixed(1),           color: fpsClass(performanceData.fps ?? 0) },
                  { label: 'Inference FPS', value: (performanceData.inference_fps ?? 0).toFixed(1), color: fpsClass(performanceData.inference_fps ?? 0) },
                  { label: 'WS Connections', value: performanceData.active_ws ?? 0,                 color: 'text-slate-700' },
                  { label: 'Model Status',  value: performanceData.model_loaded ? 'Active' : 'Inactive', color: performanceData.model_loaded ? 'text-emerald-600' : 'text-red-600' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="text-center p-4 bg-slate-50 rounded-lg">
                    <p className={`text-3xl font-light ${color}`}>{value}</p>
                    <p className="text-sm text-slate-500 mt-1">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}