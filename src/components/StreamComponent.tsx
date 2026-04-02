'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Header from '@/components/layout/Header'

interface StreamComponentProps {
  /** contoh: ws://localhost:8000 */
  apiUrl?: string;
  userFullName?: string; 
}

/** Sesuaikan dengan payload /api/performance backend-mu */
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

/** Preview lokal via halaman player MediaMTX (IFRAME) */
const IFRAME_PREVIEW_URL = 'http://192.168.2.2:8889/cam/';

type Profile = 'balanced' | 'ultra';        // balanced=TCP, ultra=UDP
type Codec = 'h264' | 'vp8';
type SourceMode = 'server' | 'device';

export default function StreamComponent({
  apiUrl = 'ws://localhost:8000',
  userFullName,  
}: StreamComponentProps) {
  const remoteVideoRef = useRef<HTMLVideoElement>(null); // hasil deteksi dari backend
  const localVideoRef = useRef<HTMLVideoElement>(null);  // hanya dipakai jika "device" dipilih

  const [isClient, setIsClient] = useState(false);
  const [clientId, setClientId] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connected' | 'error'>('disconnected');
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [performanceData, setPerformanceData] = useState<PerformanceData | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recordingId, setRecordingId] = useState<string | null>(null);

  // UI controls
  const [source, setSource] = useState<SourceMode>('server');
  const [profile, setProfile] = useState<Profile>('balanced');
  const [codec, setCodec] = useState<Codec>('h264');
  const [bitrateKbps, setBitrateKbps] = useState<number>(3500);
  const [targetFps, setTargetFps] = useState<number>(30);

  // RTC & WS
  const websocketRef = useRef<WebSocket | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const perfIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const addLog = useCallback((msg: string) => {
    const t = new Date().toLocaleTimeString();
    setLogs(prev => [`[${t}] ${msg}`, ...prev.slice(0, 99)]);
  }, []);

  useEffect(() => {
    setIsClient(true);
    setClientId(Math.random().toString(36).substring(7));
  }, []);

  // --- Model info (best-effort) ---
  useEffect(() => {
    if (!isClient) return;
    const fetchModelInfo = async () => {
      try {
        const httpUrl = apiUrl.replace('ws://', 'http://').replace('wss://', 'https://');
        const res = await fetch(`${httpUrl}/api/model-info`);
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

  // --- Performance polling ---
  useEffect(() => {
    if (!isClient) return;
    const poll = async () => {
      try {
        const httpUrl = apiUrl.replace('ws://', 'http://').replace('wss://', 'https://');
        const res = await fetch(`${httpUrl}/api/performance`);
        const data = await res.json();
        setPerformanceData(data);
      } catch {
        // ignore
      }
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

  // --- WebRTC bootstrap ---
  const initializeWebRTC = async () => {
    if (!isClient || !clientId) return;
    try {
      setConnectionStatus('disconnected');
      addLog('Init WebRTC...');

      // WS signaling
      websocketRef.current = new WebSocket(`${apiUrl}/ws/${clientId}`);
      websocketRef.current.onopen = () => {
        setConnectionStatus('connected');
        addLog('WebSocket connected');
      };
      websocketRef.current.onmessage = async (event) => {
        try {
          await handleMessage(JSON.parse(event.data));
        } catch {
          addLog('WS message parse error');
        }
      };
      websocketRef.current.onerror = () => {
        setConnectionStatus('error');
        addLog('WebSocket error');
      };
      websocketRef.current.onclose = (ev) => {
        setConnectionStatus('disconnected');
        addLog(`WebSocket closed: ${ev.code}`);
      };

      // RTCPeerConnection
      peerConnectionRef.current = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
          { urls: 'stun:stun2.l.google.com:19302' },
        ],
        iceCandidatePoolSize: 10,
      });

      peerConnectionRef.current.ontrack = (ev) => {
        if (remoteVideoRef.current && ev.streams[0]) {
          remoteVideoRef.current.srcObject = ev.streams[0];
        }
        addLog('Remote track received');
      };

      peerConnectionRef.current.onicecandidate = (ev) => {
        if (ev.candidate && websocketRef.current) {
          websocketRef.current.send(JSON.stringify({ type: 'ice-candidate', candidate: ev.candidate }));
        }
      };

      peerConnectionRef.current.onconnectionstatechange = () => {
        addLog(`RTC state: ${peerConnectionRef.current?.connectionState}`);
      };

      peerConnectionRef.current.oniceconnectionstatechange = () => {
        addLog(`ICE state: ${peerConnectionRef.current?.iceConnectionState}`);
      };
    } catch {
      setConnectionStatus('error');
      addLog('Init WebRTC failed');
    }
  };

  // --- Codec preference helper ---
  const applyCodecPreference = (transceiver: RTCRtpTransceiver, wanted: Codec) => {
    try {
      // Beberapa browser punya getCapabilities di Sender/Receiver; pakai yang ada.
      // @ts-ignore
      const rxCaps = (window as any).RTCRtpReceiver?.getCapabilities?.('video');
      // @ts-ignore
      const txCaps = (window as any).RTCRtpSender?.getCapabilities?.('video');
      const caps = rxCaps || txCaps;
      if (!caps?.codecs?.length) return;

      const isH264 = wanted === 'h264';
      const primary = caps.codecs.filter(
        (c: { mimeType?: string }) =>
          c.mimeType?.toLowerCase().includes(isH264 ? 'h264' : 'vp8')
      );
      const secondary = caps.codecs.filter(
        (c: { mimeType?: string }) =>
          !c.mimeType?.toLowerCase().includes(isH264 ? 'h264' : 'vp8')
      );

      const prefs = [...primary, ...secondary];
      // Safari/Firefox/Chrome modern mendukung ini
      // @ts-ignore
      if (transceiver.setCodecPreferences && prefs.length) {
        // @ts-ignore
        transceiver.setCodecPreferences(prefs);
        addLog(`Codec preference set: ${wanted.toUpperCase()}`);
      }
    } catch {
      // noop
    }
  };

  // --- Start (server RTSP recvonly) ---
  const startServerStream = async () => {
    addLog(`Start SERVER (codec=${codec}, profile=${profile}, bitrate=${bitrateKbps} kbps, fps=${targetFps})`);
    const pc = peerConnectionRef.current;
    if (!pc) throw new Error('RTCPeerConnection not ready');

    // Kami RECv-only (server yang kirim), tapi kita masih bisa memberi preferensi codec via transceiver
    const trx = pc.addTransceiver('video', { direction: 'recvonly' });
    applyCodecPreference(trx, codec);

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'offer',
        sdp: offer.sdp,
        // Optional metadata — backend boleh abaikan jika belum dipakai
        profile,              // 'balanced' (TCP) | 'ultra' (UDP)
        codec,                // 'h264' | 'vp8'
        maxBitrateKbps: bitrateKbps,
        targetFps,
        // Jika backendmu membaca URL RTSP dari env, tak perlu kirim di sini
      }));
      addLog('Offer (server) sent');
    } else {
      throw new Error('WebSocket not connected');
    }
  };

  // --- Start (device camera - optional) ---
  const startDeviceStream = async () => {
    addLog(`Start DEVICE (codec=${codec}, bitrate=${bitrateKbps} kbps, fps=${targetFps})`);
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280, max: 1920 },
        height: { ideal: 720, max: 1080 },
        frameRate: { ideal: targetFps, max: targetFps },
        facingMode: 'environment',
      },
      audio: false,
    });
    localStreamRef.current = stream;
    if (localVideoRef.current) localVideoRef.current.srcObject = stream;

    const pc = peerConnectionRef.current;
    if (!pc) throw new Error('RTCPeerConnection not ready');
    stream.getTracks().forEach(t => pc.addTrack(t, stream));

    // (Optional) prefer codec untuk jalur upstream (kalau backend menerima kiriman kamera klien)
    const sender = pc.getSenders().find(s => s.track?.kind === 'video');
    const trx = sender?.transport ? (sender as any).transport : null;
    // Tidak semua browser expose transceiver dari sender, jadi kita skip.

    const offer = await pc.createOffer({ offerToReceiveVideo: true, offerToReceiveAudio: false });
    await pc.setLocalDescription(offer);
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'offer',
        sdp: offer.sdp,
        profile,
        codec,
        maxBitrateKbps: bitrateKbps,
        targetFps,
      }));
      addLog('Offer (device) sent');
    } else {
      throw new Error('WebSocket not connected');
    }
  };

  const startStream = async () => {
    try {
      if (source === 'server') await startServerStream();
      else await startDeviceStream();
      setIsStreaming(true);
      addLog('Stream started');
    } catch (e: any) {
      addLog(`Start failed: ${e?.message || String(e)}`);
    }
  };

  const stopStream = () => {
    try {
      addLog('Stopping...');

      // Stop recording if active
      if (isRecording) {
        stopRecording();
      }

      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach(t => t.stop());
        localStreamRef.current = null;
      }
      if (localVideoRef.current) localVideoRef.current.srcObject = null;
      if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;

      if (peerConnectionRef.current) {
        peerConnectionRef.current.getSenders().forEach(s => {
          try { s.track?.stop(); } catch {}
        });
        peerConnectionRef.current.close();
        peerConnectionRef.current = null;
      }

      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }

      if (perfIntervalRef.current) {
        clearInterval(perfIntervalRef.current);
        perfIntervalRef.current = null;
      }

      setIsStreaming(false);
      setConnectionStatus('disconnected');
      setPerformanceData(null);
      addLog('Stopped');
    } catch {
      addLog('Stop error');
    }
  };

  // Recording functions
  const startRecording = async () => {
    if (!isStreaming || !clientId) {
      addLog('Cannot start recording: Not streaming');
      return;
    }

    try {
      const httpUrl = apiUrl.replace('ws://', 'http://').replace('wss://', 'https://');
      const response = await fetch(`${httpUrl}/api/recording/start/${clientId}`, {
        method: 'POST',
      });
      const data = await response.json();

      if (data.success) {
        setIsRecording(true);
        setRecordingId(data.recording_id);
        addLog(`Recording started: ${data.recording_id}`);
      } else {
        addLog(`Failed to start recording: ${data.error}`);
      }
    } catch (e: any) {
      addLog(`Recording error: ${e?.message || String(e)}`);
    }
  };

  const stopRecording = async () => {
    if (!isRecording || !clientId) {
      return;
    }

    try {
      const httpUrl = apiUrl.replace('ws://', 'http://').replace('wss://', 'https://');
      const response = await fetch(`${httpUrl}/api/recording/stop/${clientId}`, {
        method: 'POST',
      });
      const data = await response.json();

      if (data.success) {
        setIsRecording(false);
        const duration = data.recording?.duration || 0;
        const fileSize = data.recording?.file_size || 0;
        addLog(`Recording stopped: ${duration.toFixed(1)}s, ${(fileSize/1024/1024).toFixed(2)}MB`);
        setRecordingId(null);
      } else {
        addLog(`Failed to stop recording: ${data.error}`);
      }
    } catch (e: any) {
      addLog(`Stop recording error: ${e?.message || String(e)}`);
      setIsRecording(false);
      setRecordingId(null);
    }
  };

  const handleMessage = async (msg: any) => {
    const pc = peerConnectionRef.current;
    if (!pc) return;
    try {
      switch (msg.type) {
        case 'answer':
          await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: msg.sdp }));
          addLog('Answer set');
          break;
        case 'ice-candidate':
          if (msg.candidate) await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
          break;
        default:
          break;
      }
    } catch {
      addLog('Process WS message failed');
    }
  };

  useEffect(() => {
    if (isClient && clientId) {
      initializeWebRTC();
      return () => { stopStream(); };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClient, clientId]);

  const getStatusColor = (s: string) =>
    s === 'connected' ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : s === 'error' ? 'bg-red-50 text-red-700 border-red-200'
      : 'bg-slate-50 text-slate-700 border-slate-200';

  const getIndicator = (s: string) =>
    s === 'connected' ? <div className="w-2 h-2 bg-emerald-500 rounded-full" /> :
    s === 'error' ? <div className="w-2 h-2 bg-red-500 rounded-full" /> :
    <div className="w-2 h-2 bg-slate-400 rounded-full" />;

  const fpsClass = (v: number) => (v >= 25 ? 'text-emerald-600' : v >= 15 ? 'text-amber-600' : 'text-red-600');

  if (!isClient) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-3xl font-light text-slate-900 mb-2">Carter Island Detection System</h1>
          <p className="text-slate-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
        <Header title={'Live Stream'} subtitle={'Live Stream Monitoring 🌊'} emoji={''} />
        <div className="p-6">
          <div className="max-w-7xl mx-auto space-y-6">
            

            {/* Status & Controls */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className={`px-4 py-2 rounded-lg border text-sm font-medium flex items-center gap-2 ${getStatusColor(connectionStatus)}`}>
                    {getIndicator(connectionStatus)}
                    Status: {connectionStatus === 'error' ? 'websocket error' : connectionStatus}
                  </div>
                  {performanceData && (
                    <>
                      {performanceData.device && (
                        <div className="px-3 py-2 bg-slate-50 rounded-lg border border-slate-200">
                          <span className="text-slate-700 text-sm font-medium">Device: {performanceData.device}</span>
                        </div>
                      )}
                      {performanceData.cuda_available && (
                        <div className="px-3 py-2 bg-emerald-50 rounded-lg border border-emerald-200">
                          <span className="text-emerald-700 text-sm font-medium">CUDA Enabled</span>
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-3">
                  {/* Source */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">Source:</span>
                    <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
                      <button onClick={() => setSource('server')}
                              className={`px-3 py-1.5 text-sm ${source === 'server' ? 'bg-slate-900 text-white' : 'bg-white text-slate-700'}`}>
                        Server RTSP
                      </button>
                      <button onClick={() => setSource('device')}
                              className={`px-3 py-1.5 text-sm ${source === 'device' ? 'bg-slate-900 text-white' : 'bg-white text-slate-700'}`}>
                        Device Cam
                      </button>
                    </div>
                  </div>

                  {/* Profile */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">Profile:</span>
                    <select
                      value={profile}
                      onChange={e => setProfile(e.target.value as Profile)}
                      className="border border-slate-300 rounded-lg px-2 py-1 text-sm"
                      title="Balanced=TCP (stabil), Ultra=UDP (latency rendah)"
                    >
                      <option value="balanced">Balanced (TCP)</option>
                      <option value="ultra">Ultra-Low (UDP)</option>
                    </select>
                  </div>

                  {/* Codec */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">Codec:</span>
                    <select
                      value={codec}
                      onChange={e => setCodec(e.target.value as Codec)}
                      className="border border-slate-300 rounded-lg px-2 py-1 text-sm"
                    >
                      <option value="h264">H.264</option>
                      <option value="vp8">VP8</option>
                    </select>
                  </div>

                  {/* Bitrate */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">Bitrate (kbps):</span>
                    <input
                      type="number"
                      min={500}
                      max={12000}
                      step={100}
                      value={bitrateKbps}
                      onChange={e => setBitrateKbps(Number(e.target.value))}
                      className="w-24 border border-slate-300 rounded-lg px-2 py-1 text-sm"
                    />
                  </div>
                </div>

                {/* Transport */}
                <div className="flex gap-3">
                  <button onClick={() => window.location.reload()} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm">
                    Refresh
                  </button>
                  <button
                    onClick={startStream}
                    disabled={isStreaming || connectionStatus !== 'connected'}
                    className="px-6 py-2 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 text-white rounded-lg font-medium text-sm"
                  >
                    {isStreaming ? 'Streaming...' : 'Start Stream'}
                  </button>
                  <button
                    onClick={stopStream}
                    disabled={!isStreaming}
                    className="px-6 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-400 text-white rounded-lg font-medium text-sm"
                  >
                    Stop Stream
                  </button>

                  {/* Recording Controls */}
                  {isStreaming && (
                    <>
                      {!isRecording ? (
                        <button
                          onClick={startRecording}
                          className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium text-sm flex items-center gap-2"
                        >
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <circle cx="10" cy="10" r="6" />
                          </svg>
                          Record
                        </button>
                      ) : (
                        <button
                          onClick={stopRecording}
                          className="px-6 py-2 bg-red-800 hover:bg-red-900 text-white rounded-lg font-medium text-sm flex items-center gap-2 animate-pulse"
                        >
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <rect x="6" y="6" width="8" height="8" />
                          </svg>
                          Stop Recording
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Video Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left: Preview lokal via IFRAME (server RTSP) atau Device preview */}
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="border-b border-slate-200 px-4 py-3">
                  <h3 className="text-md font-medium text-slate-900">
                    {source === 'server' ? 'Preview (MediaMTX)' : 'Input Preview (Device)'}
                  </h3>
                </div>
                <div className="p-4">
                  <div className="relative bg-slate-900 rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
                    {source === 'server' ? (
                      <iframe
                        src={IFRAME_PREVIEW_URL}
                        className="w-full h-full"
                        allow="autoplay; encrypted-media; picture-in-picture"
                        referrerPolicy="no-referrer"
                        allowFullScreen
                      />
                    ) : (
                      <video
                        ref={localVideoRef}
                        autoPlay
                        muted
                        playsInline
                        className="w-full h-full object-cover"
                      />
                    )}
                    {!isStreaming && source === 'device' && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="text-center text-slate-400">
                          <div className="text-2xl mb-2">Device</div>
                          <p className="text-sm">Not Active</p>
                        </div>
                      </div>
                    )}
                  </div>
                  {source === 'server' && (
                    <p className="text-xs text-slate-500 mt-2">Preview dari: {IFRAME_PREVIEW_URL}</p>
                  )}
                </div>
              </div>

              {/* Right: Hasil deteksi dari backend */}
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="border-b border-slate-200 px-4 py-3">
                  <h3 className="text-md font-medium text-slate-900">YOLO Detection (WebRTC)</h3>
                </div>
                <div className="p-4">
                  <div className="relative bg-slate-900 rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
                    <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
                    {!isStreaming && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="text-center text-slate-400">
                          <div className="text-2xl mb-2">YOLO</div>
                          <p className="text-sm">No Stream</p>
                        </div>
                      </div>
                    )}
                    {isStreaming && (
                      <div className="absolute top-2 left-2 bg-red-500 text-white px-2 py-1 rounded text-xs font-medium">
                        LIVE
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Logs */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="border-b border-slate-200 px-4 py-3">
                <h3 className="text-md font-medium text-slate-900">System Logs</h3>
              </div>
              <div className="p-4">
                <div className="bg-slate-900 rounded-lg p-4 h-44 overflow-y-auto">
                  <div className="space-y-1 text-sm font-mono">
                    {logs.length ? logs.map((l, i) => <div key={i} className="text-emerald-400">{l}</div>) : <div className="text-slate-500">No logs</div>}
                  </div>
                </div>
              </div>
            </div>

            {/* Performance */}
            {performanceData && isStreaming && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <h3 className="text-lg font-medium text-slate-900 mb-4">Performance Monitor</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-4 bg-slate-50 rounded-lg">
                    <p className={`text-3xl font-light ${fpsClass(performanceData.fps ?? 0)}`}>{(performanceData.fps ?? 0).toFixed(1)}</p>
                    <p className="text-sm text-slate-600 mt-1">Render FPS</p>
                  </div>
                  <div className="text-center p-4 bg-slate-50 rounded-lg">
                    <p className={`text-3xl font-light ${fpsClass(performanceData.inference_fps ?? 0)}`}>{(performanceData.inference_fps ?? 0).toFixed(1)}</p>
                    <p className="text-sm text-slate-600 mt-1">Inference FPS</p>
                  </div>
                  <div className="text-center p-4 bg-slate-50 rounded-lg">
                    <p className="text-3xl font-light text-slate-700">{performanceData.active_ws ?? 0}</p>
                    <p className="text-sm text-slate-600 mt-1">WS Connections</p>
                  </div>
                  <div className="text-center p-4 bg-slate-50 rounded-lg">
                    <p className="text-3xl font-light text-slate-700">{performanceData.model_loaded ? 'Active' : 'Inactive'}</p>
                    <p className="text-sm text-slate-600 mt-1">Model Status</p>
                  </div>
                </div>
              </div>
            )}

            {/* Notes */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h3 className="text-lg font-medium text-slate-900 mb-3">Catatan</h3>
              <ul className="list-disc list-inside text-sm text-slate-600 space-y-2">
                <li>Panel kiri (Server RTSP) hanya **preview** via IFRAME. Input deteksi tetap di-pull dari RTSP oleh backend (latency rendah, stabil).</li>
                <li>Kontrol <b>Codec / Profile / Bitrate / FPS</b> dikirim via signaling. Backend boleh mengabaikan bila belum diimplementasikan.</li>
                <li>Jika ingin benar-benar enforce bitrate/codec dari sisi server, perlu dukungan di backend (mis. setSenderParameters/SDP munging).</li>
              </ul>
            </div>
          </div>
        </div>
    </div>
  );
}
