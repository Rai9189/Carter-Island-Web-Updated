'use client'

import { useState, useMemo } from 'react'
import { toast } from 'sonner'
import { apiClient } from '@/lib/api-client'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'

interface Recording {
  id: string
  sessionId: string
  fileName: string
  filePath: string
  fileSize: number
  format: string
  duration: number | null
  createdAt: string
  updatedAt: string
  // field tambahan dari dialog simpan recording
  missionName?: string
  location?: string
}

interface RecordingsTableProps {
  recordings: Recording[]
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '--'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '—'
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatTimeRange(dateStr: string, duration: number | null): string {
  const start = new Date(dateStr)
  const startStr = start.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
  if (!duration) return startStr
  const end = new Date(start.getTime() + duration * 1000)
  const endStr = end.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
  return `${startStr}-${endStr}`
}

const FORMAT_ALL = 'Semua'
const SORT_NEWEST = 'Terbaru'
const SORT_OLDEST = 'Terlama'

const FORMAT_COLORS: Record<string, string> = {
  mp4: 'bg-blue-100 text-blue-700',
  webm: 'bg-purple-100 text-purple-700',
  avi: 'bg-orange-100 text-orange-700',
}

export default function RecordingsTable({ recordings: initialRecordings }: RecordingsTableProps) {
  const [recordings, setRecordings] = useState(initialRecordings)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [playingVideo, setPlayingVideo] = useState<Recording | null>(null)
  const [search, setSearch] = useState('')
  const [formatFilter, setFormatFilter] = useState(FORMAT_ALL)
  const [sortOrder, setSortOrder] = useState(SORT_NEWEST)

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  const filtered = useMemo(() => {
    let list = [...recordings]
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(r =>
        (r.missionName ?? r.fileName).toLowerCase().includes(q) ||
        r.sessionId.toLowerCase().includes(q)
      )
    }
    if (formatFilter !== FORMAT_ALL) {
      list = list.filter(r => r.format.toLowerCase() === formatFilter.toLowerCase())
    }
    if (sortOrder === SORT_NEWEST) {
      list.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    } else {
      list.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
    }
    return list
  }, [recordings, search, formatFilter, sortOrder])

  const handleDelete = async (id: string, fileName: string) => {
    if (!confirm(`Hapus recording "${fileName}"?`)) return
    setDeletingId(id)
    try {
      await apiClient.delete(`/api/recordings/${id}`)
      setRecordings(prev => prev.filter(r => r.id !== id))
    } catch {
      toast.error('Gagal menghapus recording')
    } finally {
      setDeletingId(null)
    }
  }

  const handleDownload = (fileName: string) => {
    window.open(`${backendUrl}/api/recordings/download/${fileName}`, '_blank')
  }

  return (
    <div className="space-y-4">

      {/* ── Filter Bar ── */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-48">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Cari nama mission atau session..."
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 bg-white"
          />
        </div>

        {/* Format filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Format:</span>
          <select
            value={formatFilter}
            onChange={e => setFormatFilter(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-blue-400 cursor-pointer"
          >
            <option value={FORMAT_ALL}>{FORMAT_ALL}</option>
            <option value="MP4">MP4</option>
            <option value="WEBM">WEBM</option>
          </select>
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Urutkan:</span>
          <select
            value={sortOrder}
            onChange={e => setSortOrder(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-blue-400 cursor-pointer"
          >
            <option value={SORT_NEWEST}>{SORT_NEWEST}</option>
            <option value={SORT_OLDEST}>{SORT_OLDEST}</option>
          </select>
        </div>

        {/* Count */}
        <span className="ml-auto text-sm text-gray-400">
          {filtered.length} rekaman ditemukan
        </span>
      </div>

      {/* ── Table ── */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-300">
          <div className="w-16 h-16 rounded-full border-4 border-dashed border-gray-200 flex items-center justify-center mb-3">
            <span className="text-2xl">📹</span>
          </div>
          <p className="text-sm text-gray-400">Belum ada rekaman ditemukan</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-100">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                {['FORMAT', 'NAMA MISI', 'TANGGAL', 'WAKTU MISI', 'DURASI', 'UKURAN', 'SESSION ID', 'ACTIONS'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-400 tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(rec => (
                <tr key={rec.id} className="bg-white hover:bg-gray-50 transition-colors">
                  {/* Format badge */}
                  <td className="px-4 py-4">
                    <span className={`text-xs font-bold px-2 py-1 rounded-lg uppercase ${FORMAT_COLORS[rec.format.toLowerCase()] ?? 'bg-gray-100 text-gray-600'}`}>
                      {rec.format.toUpperCase()}
                    </span>
                  </td>

                  {/* Nama misi / file name */}
                  <td className="px-4 py-4 font-medium text-gray-800 whitespace-nowrap">
                    {rec.missionName ?? rec.fileName}
                  </td>

                  {/* Tanggal */}
                  <td className="px-4 py-4 text-gray-500 whitespace-nowrap">
                    {formatDate(rec.createdAt)}
                  </td>

                  {/* Waktu misi (start-end) */}
                  <td className="px-4 py-4 text-gray-500 whitespace-nowrap font-mono text-xs">
                    {formatTimeRange(rec.createdAt, rec.duration)}
                  </td>

                  {/* Durasi */}
                  <td className="px-4 py-4 text-gray-500 whitespace-nowrap font-mono text-xs">
                    {formatDuration(rec.duration)}
                  </td>

                  {/* Ukuran */}
                  <td className="px-4 py-4 text-gray-500 whitespace-nowrap">
                    {formatFileSize(rec.fileSize)}
                  </td>

                  {/* Session ID */}
                  <td className="px-4 py-4">
                    <span className="text-xs font-mono text-gray-400 border border-gray-200 px-2 py-1 rounded-lg bg-gray-50">
                      session_{rec.sessionId.slice(-3)}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPlayingVideo(rec)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 hover:bg-gray-700 text-white text-xs font-medium rounded-lg transition-colors"
                      >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                        Play
                      </button>
                      <button
                        onClick={() => handleDownload(rec.fileName)}
                        className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-medium rounded-lg transition-colors"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        Download
                      </button>
                      <button
                        onClick={() => handleDelete(rec.id, rec.fileName)}
                        disabled={deletingId === rec.id}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white text-xs font-medium rounded-lg transition-colors"
                      >
                        {deletingId === rec.id ? 'Menghapus...' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Video Player Dialog ── */}
      <Dialog open={!!playingVideo} onOpenChange={open => { if (!open) setPlayingVideo(null) }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold text-gray-700">
              {playingVideo?.missionName ?? playingVideo?.fileName}
            </DialogTitle>
          </DialogHeader>
          <div className="mt-2">
            {playingVideo && (
              <video
                controls
                autoPlay
                className="w-full rounded-xl bg-black"
                src={`${backendUrl}/api/recordings/stream/${playingVideo.fileName}`}
              >
                Browser tidak mendukung video tag.
              </video>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}