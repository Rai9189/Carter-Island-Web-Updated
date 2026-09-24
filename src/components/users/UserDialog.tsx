'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { apiClient } from '@/lib/api-client'

interface User {
  id: string; fullName: string; email: string; phoneNumber: string
  role: 'USER' | 'ADMIN'; createdAt: string; updatedAt: string
}

interface UserDialogProps {
  isOpen: boolean; onClose: () => void; onSuccess: () => void
  user?: User | null; mode: 'create' | 'edit' | 'view'
}

interface FormData {
  fullName: string; email: string; password: string; phoneNumber: string; role: 'USER' | 'ADMIN'
}

export default function UserDialog({ isOpen, onClose, onSuccess, user, mode }: UserDialogProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [formData, setFormData] = useState<FormData>({
    fullName: '', email: '', password: '', phoneNumber: '', role: 'USER'
  })
  const [errors, setErrors] = useState<Partial<FormData>>({})

  useEffect(() => {
    if (!isOpen) return
    setErrors({})
    if (mode === 'create') {
      setFormData({ fullName: '', email: '', password: '', phoneNumber: '', role: 'USER' })
    } else if (user) {
      setFormData({ fullName: user.fullName || '', email: user.email || '', password: '', phoneNumber: user.phoneNumber || '', role: user.role || 'USER' })
    }
  }, [isOpen, mode, user])

  const validate = () => {
    const errs: Partial<FormData> = {}
    if (!formData.fullName.trim()) errs.fullName = 'Nama lengkap wajib diisi'
    if (!formData.email.trim()) errs.email = 'Email wajib diisi'
    if (!formData.phoneNumber.trim()) errs.phoneNumber = 'No. telepon wajib diisi'
    if (mode === 'create' && !formData.password.trim()) errs.password = 'Password wajib diisi'
    if (formData.password.trim() && formData.password.length < 8) errs.password = 'Min. 8 karakter'
    return errs
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setIsLoading(true)
    try {
      const submitData: Record<string, unknown> = {
        fullName: formData.fullName, email: formData.email,
        phoneNumber: formData.phoneNumber, role: formData.role
      }
      if (mode === 'create' || formData.password.trim()) submitData.password = formData.password
      const data: any = mode === 'create'
        ? await apiClient.post('/api/users', submitData)
        : await apiClient.put(`/api/users/${user?.id}`, submitData)
      toast.success(data.message || (mode === 'create' ? 'Pengguna berhasil ditambahkan' : 'Pengguna berhasil diperbarui'))
      onSuccess()
      onClose()
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Gagal menyimpan pengguna')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    setFormData({ fullName: '', email: '', password: '', phoneNumber: '', role: 'USER' })
    setErrors({})
    onClose()
  }

  if (!isOpen) return null

  const title = mode === 'create' ? 'Tambah Pengguna Baru'
    : mode === 'edit' ? `Edit Pengguna — ${user?.fullName}`
    : `Detail Pengguna — ${user?.fullName}`

  const subtitle = mode === 'create' ? 'Isi data pengguna di bawah ini.'
    : mode === 'edit' ? 'Ubah data pengguna di bawah ini.'
    : ''

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">

        {/* Header — dark */}
        <div className="bg-gray-900 px-6 py-5 flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold text-white">{title}</h2>
            {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
          <button onClick={handleClose} className="text-gray-400 hover:text-white transition-colors text-xl leading-none mt-0.5">&times;</button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {mode === 'view' ? (
            <div className="space-y-4">
              {[
                { label: 'Nama Lengkap', value: user?.fullName },
                { label: 'Email', value: user?.email },
                { label: 'No. Telepon', value: user?.phoneNumber },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-xs text-gray-400 mb-1">{label}</p>
                  <p className="text-sm font-medium text-gray-800">{value || '—'}</p>
                </div>
              ))}
              <div>
                <p className="text-xs text-gray-400 mb-1">Role</p>
                <span className={`text-xs font-bold px-3 py-1 rounded-lg ${user?.role === 'ADMIN' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-700'}`}>
                  {user?.role}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-gray-100">
                <div>
                  <p className="text-xs text-gray-400 mb-1">Dibuat</p>
                  <p className="text-xs text-gray-600">{user?.createdAt ? new Date(user.createdAt).toLocaleDateString('id-ID') : '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1">Diperbarui</p>
                  <p className="text-xs text-gray-600">{user?.updatedAt ? new Date(user.updatedAt).toLocaleDateString('id-ID') : '—'}</p>
                </div>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Nama Lengkap */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1.5 block">
                  Nama Lengkap <span className="text-red-500">*</span>
                </label>
                <input
                  value={formData.fullName}
                  onChange={e => { setFormData(p => ({ ...p, fullName: e.target.value })); setErrors(p => ({ ...p, fullName: undefined })) }}
                  placeholder="Contoh: Jane Smith"
                  className={`w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none transition-colors ${errors.fullName ? 'border-red-300 bg-red-50' : 'border-gray-200 focus:border-blue-400'}`}
                />
                {errors.fullName && <p className="text-xs text-red-500 mt-1">{errors.fullName}</p>}
              </div>

              {/* Email */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1.5 block">
                  Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={e => { setFormData(p => ({ ...p, email: e.target.value })); setErrors(p => ({ ...p, email: undefined })) }}
                  placeholder="email@carterisland.com"
                  className={`w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none transition-colors ${errors.email ? 'border-red-300 bg-red-50' : 'border-gray-200 focus:border-blue-400'}`}
                />
                {errors.email && <p className="text-xs text-red-500 mt-1">{errors.email}</p>}
              </div>

              {/* No. Telepon + Password */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1.5 block">
                    No. Telepon <span className="text-red-500">*</span>
                  </label>
                  <input
                    value={formData.phoneNumber}
                    onChange={e => { setFormData(p => ({ ...p, phoneNumber: e.target.value })); setErrors(p => ({ ...p, phoneNumber: undefined })) }}
                    placeholder="+62-8xx-xxxx-xxxx"
                    className={`w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none transition-colors ${errors.phoneNumber ? 'border-red-300 bg-red-50' : 'border-gray-200 focus:border-blue-400'}`}
                  />
                  {errors.phoneNumber && <p className="text-xs text-red-500 mt-1">{errors.phoneNumber}</p>}
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1.5 block">
                    Password {mode === 'create' ? <span className="text-red-500">*</span> : <span className="text-gray-400 font-normal text-xs">(opsional)</span>}
                  </label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={e => { setFormData(p => ({ ...p, password: e.target.value })); setErrors(p => ({ ...p, password: undefined })) }}
                    placeholder="Min. 8 karakter"
                    className={`w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none transition-colors ${errors.password ? 'border-red-300 bg-red-50' : 'border-gray-200 focus:border-blue-400'}`}
                  />
                  {errors.password && <p className="text-xs text-red-500 mt-1">{errors.password}</p>}
                </div>
              </div>

              {/* Role — toggle pill */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Role <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setFormData(p => ({ ...p, role: 'ADMIN' }))}
                    className={`px-4 py-3 rounded-xl border-2 text-left transition-all ${formData.role === 'ADMIN' ? 'border-gray-300 bg-white' : 'border-gray-100 bg-gray-50 hover:border-gray-200'}`}
                  >
                    <p className={`text-sm font-semibold ${formData.role === 'ADMIN' ? 'text-gray-800' : 'text-gray-500'}`}>Admin</p>
                    <p className="text-xs text-gray-400 mt-0.5">Akses penuh ke sistem</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormData(p => ({ ...p, role: 'USER' }))}
                    className={`px-4 py-3 rounded-xl border-2 text-left transition-all ${formData.role === 'USER' ? 'border-blue-400 bg-blue-50' : 'border-gray-100 bg-gray-50 hover:border-gray-200'}`}
                  >
                    <p className={`text-sm font-semibold ${formData.role === 'USER' ? 'text-blue-700' : 'text-gray-500'}`}>User</p>
                    <p className="text-xs text-gray-400 mt-0.5">Akses terbatas (view only)</p>
                  </button>
                </div>
              </div>

              {/* Info */}
              {mode === 'create' && (
                <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-xl text-xs text-blue-600">
                  <span>ℹ</span>
                  <span>Password awal akan dikirim ke email pengguna.</span>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={isLoading}
                  className="flex-1 py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Menyimpan...</>
                  ) : (
                    <>{mode === 'create' ? '✓ Simpan Pengguna' : '✓ Update Pengguna'}</>
                  )}
                </button>
              </div>
            </form>
          )}

          {mode === 'view' && (
            <div className="flex justify-end mt-4">
              <button onClick={handleClose} className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition-colors">
                Tutup
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}