'use client'

import { useState } from 'react'
import Header from '@/components/layout/Header'
import UserDialog from '@/components/users/UserDialog'
import { Loader2 } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useUsersPagination, type User } from '@/hooks/useUsersPagination'
import { FiltersBar } from './FiltersBar'
import { UsersTable } from './UsersTable'
import { toast } from 'sonner'
import { apiClient } from '@/lib/api-client'

export default function UsersPage() {
  const { session, status } = useAdminGuard()
  const {
    users, isLoading, error, hasMore, loadMore, removeFromList, resetAndLoad,
    limit, setLimit, role, setRole, search, setSearch, sort, setSort
  } = useUsersPagination({ enabled: status === 'authenticated' && session?.user.role === 'ADMIN' })

  const [dialogState, setDialogState] = useState<{
    isOpen: boolean; mode: 'create' | 'edit' | 'view'; user: User | null
  }>({ isOpen: false, mode: 'create', user: null })

  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean; user: User | null; isDeleting: boolean
  }>({ isOpen: false, user: null, isDeleting: false })

  if (status === 'loading' || !session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }
  if (session.user.role !== 'ADMIN') return null

  const handleAddUser = () => setDialogState({ isOpen: true, mode: 'create', user: null })
  const handleEditUser = (user: User) => setDialogState({ isOpen: true, mode: 'edit', user })
  const handleViewUser = (user: User) => setDialogState({ isOpen: true, mode: 'view', user })
  const handleDeleteUser = (user: User) => setDeleteDialog({ isOpen: true, user, isDeleting: false })

  const confirmDelete = async () => {
    const u = deleteDialog.user
    if (!u) return
    try {
      setDeleteDialog(p => ({ ...p, isDeleting: true }))
      const data = await apiClient.delete<{ message: string }>(`/api/users/${u.id}`)
      removeFromList(u.id)
      toast.success(data?.message || 'Pengguna berhasil dihapus')
      setDeleteDialog({ isOpen: false, user: null, isDeleting: false })
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Gagal menghapus pengguna')
      setDeleteDialog(p => ({ ...p, isDeleting: false }))
    }
  }

  return (
    <>
      <Header title="User Management" subtitle="Manage System Users and Permissions" emoji="🔧" />

      <main className="px-6 py-4">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">

          <FiltersBar
            limit={limit} setLimit={setLimit}
            role={role} setRole={setRole}
            search={search} setSearch={setSearch}
            sort={sort} setSort={setSort}
            loadedCount={users.length} hasMore={hasMore}
            onAddUser={handleAddUser}
          />

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-100 rounded-xl text-sm text-red-600">
              {error}
            </div>
          )}

          {isLoading && users.length === 0 ? (
            <div className="flex items-center justify-center py-16 text-gray-400">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              <span className="text-sm">Memuat data pengguna...</span>
            </div>
          ) : users.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-300">
              <div className="w-16 h-16 rounded-full border-4 border-dashed border-gray-200 flex items-center justify-center mb-3">
                <span className="text-2xl">👤</span>
              </div>
              <p className="text-sm text-gray-400">Tidak ada pengguna ditemukan</p>
            </div>
          ) : (
            <>
              <UsersTable
                users={users}
                currentUserId={session.user.id}
                onView={handleViewUser}
                onEdit={handleEditUser}
                onDelete={handleDeleteUser}
              />

              {/* Load more */}
              {hasMore && (
                <div className="flex justify-center mt-4">
                  <button
                    onClick={loadMore}
                    disabled={isLoading}
                    className="px-6 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                  >
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Muat Lebih Banyak'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* User Dialog */}
      <UserDialog
        isOpen={dialogState.isOpen}
        onClose={() => setDialogState(s => ({ ...s, isOpen: false }))}
        onSuccess={() => resetAndLoad()}
        user={dialogState.user}
        mode={dialogState.mode}
      />

      {/* Delete Confirm Dialog */}
      {deleteDialog.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden">
            <div className="bg-red-600 px-6 py-4">
              <h2 className="text-base font-semibold text-white">Hapus Pengguna</h2>
            </div>
            <div className="px-6 py-5">
              <p className="text-sm text-gray-600 mb-4">
                Apakah Anda yakin ingin menghapus pengguna ini? Tindakan ini tidak dapat dibatalkan.
              </p>
              {deleteDialog.user && (
                <div className="p-3 bg-gray-50 rounded-xl mb-4">
                  <p className="font-medium text-gray-800 text-sm">{deleteDialog.user.fullName}</p>
                  <p className="text-xs text-gray-500">{deleteDialog.user.email}</p>
                </div>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteDialog({ isOpen: false, user: null, isDeleting: false })}
                  disabled={deleteDialog.isDeleting}
                  className="flex-1 py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                >
                  Batal
                </button>
                <button
                  onClick={confirmDelete}
                  disabled={deleteDialog.isDeleting}
                  className="flex-1 py-2.5 bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-2"
                >
                  {deleteDialog.isDeleting ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Menghapus...</>
                  ) : 'Hapus Pengguna'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}