'use client'

import { authHelper } from '@/lib/api-client'

interface LogoutButtonProps {
  className?: string
  children?: React.ReactNode
}

export default function LogoutButton({ className, children }: LogoutButtonProps) {
  const handleLogout = async () => {
    /**
     * PERUBAHAN:
     * Sebelum: signOut({ redirect: false }) dari NextAuth
     * Sesudah: authHelper.logout()
     *          → POST /api/auth/logout ke FastAPI (hapus cookie)
     *          → hapus localStorage token
     *          → redirect ke /auth/login
     */
    await authHelper.logout()
  }

  return (
    <button
      onClick={handleLogout}
      className={className || 'px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors'}
    >
      {children || 'Sign Out'}
    </button>
  )
}