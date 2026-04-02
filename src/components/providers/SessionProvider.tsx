'use client'

/**
 * SessionProvider — NextAuth tidak dipakai lagi.
 * File ini dipertahankan agar tidak perlu update semua import,
 * tapi isinya hanya meneruskan children tanpa wrapper NextAuth.
 *
 * Setelah semua import SessionProvider dibersihkan dari layout.tsx,
 * file ini bisa dihapus.
 */
interface SessionProviderProps {
  children: React.ReactNode
}

export default function SessionProvider({ children }: SessionProviderProps) {
  return <>{children}</>
}