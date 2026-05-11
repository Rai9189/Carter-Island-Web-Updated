'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  HelpCircle, Info, Clock, Mail, ChevronDown, ChevronUp,
  Wifi, Fish, Video, BarChart2, Map, Settings
} from 'lucide-react'

// ── FAQ Data ──
const FAQ_ITEMS = [
  {
    category: 'Sesi Misi',
    icon: Map,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    questions: [
      {
        q: 'Bagaimana cara memulai sesi misi?',
        a: 'Buka halaman Live Stream, klik tombol "Mulai Sesi Misi" di bagian atas, masukkan nama lokasi survei, lalu klik "Mulai". Sesi akan otomatis dicatat dengan waktu mulai dan semua data (deteksi, telemetri, recording) akan terhubung ke sesi tersebut.',
      },
      {
        q: 'Apa yang terjadi jika sesi tidak diselesaikan?',
        a: 'Sesi yang masih berstatus "Running" akan tetap aktif hingga operator secara manual menyelesaikannya (Completed) atau membatalkannya (Aborted). Data tetap tersimpan. Disarankan selalu menyelesaikan sesi setelah misi selesai.',
      },
      {
        q: 'Bisakah ada lebih dari satu sesi aktif sekaligus?',
        a: 'Tidak. Sistem hanya mengizinkan satu sesi berstatus Running pada satu waktu. Selesaikan sesi yang berjalan sebelum memulai sesi baru.',
      },
    ],
  },
  {
    category: 'Live Stream',
    icon: Video,
    color: 'text-red-600',
    bg: 'bg-red-50',
    questions: [
      {
        q: 'Mengapa video preview tidak muncul?',
        a: 'Pastikan ROV dan Raspberry Pi sudah terhubung ke jaringan yang sama dengan Base Station. Preview kiri menggunakan MediaMTX di alamat 192.168.2.2:8889. Pastikan alamat tersebut dapat diakses dari browser.',
      },
      {
        q: 'Apa perbedaan panel kiri dan panel kanan?',
        a: 'Panel kiri adalah preview langsung dari kamera via MediaMTX (RTSP). Panel kanan adalah hasil deteksi YOLO yang diproses backend dan dikirim via WebRTC — menampilkan bounding box di sekitar ikan yang terdeteksi.',
      },
      {
        q: 'Kapan tombol Record bisa digunakan?',
        a: 'Tombol Record hanya muncul setelah streaming aktif (Start Stream berhasil). Klik Record untuk mulai merekam, dan Stop Recording untuk mengakhiri. File video otomatis tersimpan dan bisa dilihat di halaman Recordings.',
      },
    ],
  },
  {
    category: 'Deteksi Ikan',
    icon: Fish,
    color: 'text-teal-600',
    bg: 'bg-teal-50',
    questions: [
      {
        q: 'Spesies apa saja yang bisa dideteksi?',
        a: 'Model YOLOv8 yang digunakan (16sept.pt) dilatih untuk mendeteksi spesies ikan karang di perairan Carter Island. Daftar spesies tersedia di panel AI Species Counter saat streaming berlangsung.',
      },
      {
        q: 'Mengapa AI Species Counter tidak update?',
        a: 'Species Counter hanya aktif jika ada sesi misi yang berjalan DAN streaming aktif. Pastikan keduanya sudah dimulai. Counter update setiap 5 detik dari database.',
      },
      {
        q: 'Apakah data deteksi tersimpan otomatis?',
        a: 'Ya. Setiap deteksi YOLO otomatis disimpan ke database selama variabel SAVE_DETECTIONS_ENABLED=true di konfigurasi backend. Data bisa dilihat di halaman Analytics.',
      },
    ],
  },
  {
    category: 'Analytics & Historical',
    icon: BarChart2,
    color: 'text-purple-600',
    bg: 'bg-purple-50',
    questions: [
      {
        q: 'Bagaimana cara melihat data per sesi?',
        a: 'Di halaman Analytics, gunakan dropdown "Semua Sesi" untuk memilih sesi tertentu. Chart akan otomatis memfilter data sesuai sesi yang dipilih. Di halaman Historical, klik baris sesi untuk melihat detailnya.',
      },
      {
        q: 'Bagaimana cara export data ke CSV?',
        a: 'Di halaman Historical, klik tombol "Export CSV" untuk mengunduh riwayat semua sesi. Untuk mengunduh data deteksi spesifik satu sesi, klik baris sesi lalu klik "Export Deteksi".',
      },
    ],
  },
  {
    category: 'Koneksi & Sensor',
    icon: Wifi,
    color: 'text-indigo-600',
    bg: 'bg-indigo-50',
    questions: [
      {
        q: 'Data apa saja yang ditampilkan di Dashboard?',
        a: 'Dashboard menampilkan data kualitas air real-time (pH, TDS, Dissolved Oxygen, suhu) dari sensor ROV, serta data navigasi (roll, pitch, yaw, heading, depth, speed) dari IMU Pixhawk.',
      },
      {
        q: 'Mengapa data Dashboard menampilkan tanda --?',
        a: 'Tanda -- berarti belum ada data dari sensor. Pastikan ROV terhubung dan ada sesi misi yang aktif agar data telemetri tersimpan ke database.',
      },
    ],
  },
]

// ── Changelog Data ──
const CHANGELOG = [
  {
    version: 'v5.0.0',
    date: 'Mei 2026',
    changes: [
      'Migrasi dari Next.js API Routes ke FastAPI backend',
      'Struktur database baru sesuai dokumen C300 — monitoring_sessions sebagai hub utama',
      'Data telemetri berubah: dari navigasi ROV ke kualitas air (pH, TDS, DO, suhu)',
      'Tambah tabel fish_counts, video_paths, video_stream',
      'Session management — mulai/selesaikan sesi misi dari halaman Stream',
      'AI Species Counter di halaman Stream',
      'Halaman Historical Data dengan export CSV',
      'Filter by sesi di halaman Analytics',
    ],
  },
  {
    version: 'v4.0.0',
    date: 'Maret 2026',
    changes: [
      'Integrasi WebRTC untuk live streaming YOLO detection',
      'Recording video langsung dari browser',
      'APScheduler untuk health check otomatis',
      'JWT authentication menggantikan NextAuth',
    ],
  },
  {
    version: 'v3.0.0',
    date: 'Januari 2026',
    changes: [
      'Dashboard real-time dengan SWR polling',
      'Halaman Analytics dengan Recharts',
      'Manajemen user dengan role ADMIN/USER',
    ],
  },
]

// ── System Info ──
const SYSTEM_INFO = [
  { label: 'Versi Sistem',       value: 'v5.0.0' },
  { label: 'Backend',            value: 'FastAPI + SQLAlchemy' },
  { label: 'Frontend',           value: 'Next.js 15 + TypeScript' },
  { label: 'Database',           value: 'MySQL 8.0' },
  { label: 'Model AI',           value: 'YOLOv8 (16sept.pt)' },
  { label: 'Streaming Protocol', value: 'WebRTC + MediaMTX (RTSP)' },
  { label: 'ROV IMU',            value: 'Pixhawk (MAVLink)' },
  { label: 'IP Raspberry Pi',    value: '192.168.2.2' },
]

function FAQItem({ question, answer }: { question: string; answer: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="text-sm font-medium text-gray-800 pr-4">{question}</span>
        {open
          ? <ChevronUp className="h-4 w-4 text-gray-400 flex-shrink-0" />
          : <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1">
          <p className="text-sm text-gray-600 leading-relaxed">{answer}</p>
        </div>
      )}
    </div>
  )
}

export default function HelpContent() {
  const [activeCategory, setActiveCategory] = useState<string | null>(null)

  return (
    <div className="space-y-6 pb-8">

      {/* ── Quick Nav ── */}
      <div className="flex flex-wrap gap-2">
        {FAQ_ITEMS.map(({ category, icon: Icon, color, bg }) => (
          <button
            key={category}
            onClick={() => setActiveCategory(
              activeCategory === category ? null : category
            )}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
              activeCategory === category
                ? `${bg} ${color} border-current`
                : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {category}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Kiri: FAQ */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <HelpCircle className="h-5 w-5 text-blue-500" />
                Frequently Asked Questions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {FAQ_ITEMS
                .filter(f => !activeCategory || f.category === activeCategory)
                .map(({ category, icon: Icon, color, bg, questions }) => (
                  <div key={category}>
                    <div className={`flex items-center gap-2 mb-3 px-3 py-1.5 rounded-lg ${bg} w-fit`}>
                      <Icon className={`h-4 w-4 ${color}`} />
                      <span className={`text-xs font-semibold uppercase tracking-wide ${color}`}>
                        {category}
                      </span>
                    </div>
                    <div className="space-y-2">
                      {questions.map(({ q, a }) => (
                        <FAQItem key={q} question={q} answer={a} />
                      ))}
                    </div>
                  </div>
                ))}
            </CardContent>
          </Card>
        </div>

        {/* Kanan: Info Sistem + Changelog + Kontak */}
        <div className="space-y-4">

          {/* Info Sistem */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Info className="h-5 w-5 text-indigo-500" />
                Info Sistem
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {SYSTEM_INFO.map(({ label, value }) => (
                  <div key={label} className="flex justify-between items-center text-sm py-1.5 border-b border-gray-50 last:border-0">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-medium text-gray-800 text-right ml-2">{value}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Kontak Admin */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Mail className="h-5 w-5 text-green-500" />
                Kontak & Dukungan
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="p-3 bg-green-50 rounded-xl text-sm">
                <p className="font-medium text-green-800 mb-1">Tim Pengembang</p>
                <p className="text-green-700">Carter Island AUV Team</p>
                <p className="text-green-600 text-xs mt-1">Capstone Project TA 2026</p>
              </div>
              <div className="p-3 bg-blue-50 rounded-xl text-sm">
                <p className="font-medium text-blue-800 mb-1">Email Admin</p>
                <p className="text-blue-700">admin@carterisland.com</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-xl text-sm">
                <p className="font-medium text-gray-700 mb-1">API Documentation</p>
                <a
                  href="http://localhost:8000/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline text-xs"
                >
                  localhost:8000/docs →
                </a>
              </div>
            </CardContent>
          </Card>

          {/* Changelog */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Clock className="h-5 w-5 text-orange-500" />
                Changelog
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {CHANGELOG.map(({ version, date, changes }, i) => (
                  <div key={version} className="relative pl-4 border-l-2 border-gray-100">
                    <div className="absolute -left-1.5 top-1 w-3 h-3 rounded-full bg-white border-2 border-blue-400" />
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`text-sm font-bold ${i === 0 ? 'text-blue-600' : 'text-gray-600'}`}>
                        {version}
                      </span>
                      <span className="text-xs text-gray-400">{date}</span>
                      {i === 0 && (
                        <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded font-medium">
                          Latest
                        </span>
                      )}
                    </div>
                    <ul className="space-y-1">
                      {changes.map(c => (
                        <li key={c} className="text-xs text-gray-500 flex items-start gap-1.5">
                          <span className="text-blue-400 mt-0.5 flex-shrink-0">•</span>
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

        </div>
      </div>
    </div>
  )
}