'use client';

import { Button } from '@/components/ui/button';
import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api-client';

interface Recording {
  id: string;
  filename: string;
  fileSize: string; // BigInt dari FastAPI dikembalikan sebagai string
  duration: number;
  startTime: string;
  sessionId: string;
}

interface RecordingsTableProps {
  recordings: Recording[];
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatFileSize(bytes: string): string {
  const size = Number(bytes);
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('id-ID', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(dateStr));
}

export default function RecordingsTable({ recordings }: RecordingsTableProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [playingVideo, setPlayingVideo] = useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const backendUrl =
    process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleDelete = async (id: string, filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;

    setDeletingId(id);
    try {
      /**
       * PERUBAHAN:
       * Sebelum: fetch(`/api/recordings?id=${id}`, { method: 'DELETE' })
       * Sesudah: apiClient.delete(`/api/recordings/${id}`)
       *
       * FastAPI pakai path param, bukan query param.
       * apiClient otomatis kirim JWT token.
       */
      await apiClient.delete(`/api/recordings/${id}`)
      window.location.reload();
    } catch (error) {
      console.error('Error deleting recording:', error);
      alert('Failed to delete recording');
      setDeletingId(null);
    }
  };

  const handlePlay = (filename: string) => {
    setPlayingVideo(filename);
    setIsDialogOpen(true);
  };

  const handleDownload = (filename: string) => {
    /**
     * TIDAK BERUBAH — download tetap langsung ke FastAPI backend
     * karena StreamComponent juga sudah pakai NEXT_PUBLIC_API_URL
     */
    const downloadUrl = `${backendUrl}/api/recordings/download/${filename}`;
    window.open(downloadUrl, '_blank');
  };

  if (recordings.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">No recordings</h3>
        <p className="mt-1 text-sm text-gray-500">
          Start recording from the livestream to see your recordings here.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {['Filename', 'Duration', 'Size', 'Date', 'Session ID', 'Actions'].map((h) => (
                <th
                  key={h}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {recordings.map((recording) => (
              <tr key={recording.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {recording.filename}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDuration(recording.duration)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatFileSize(recording.fileSize)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(recording.startTime)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono text-xs">
                  {recording.sessionId.substring(0, 8)}...
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                  <Button size="sm" onClick={() => handlePlay(recording.filename)}>
                    Play
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleDownload(recording.filename)}
                  >
                    Download
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(recording.id, recording.filename)}
                    disabled={deletingId === recording.id}
                  >
                    {deletingId === recording.id ? 'Deleting...' : 'Delete'}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Video Playback — {playingVideo}</DialogTitle>
          </DialogHeader>
          <div className="mt-4">
            {playingVideo && (
              <video
                controls
                autoPlay
                className="w-full rounded-lg"
                src={`${backendUrl}/api/recordings/stream/${playingVideo}`}
              >
                Your browser does not support the video tag.
              </video>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}