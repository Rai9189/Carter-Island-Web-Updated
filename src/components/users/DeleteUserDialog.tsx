'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { toast } from 'sonner'
import { AlertTriangle } from 'lucide-react'
import { apiClient } from '@/lib/api-client'

interface User {
  id: string
  fullName: string
  email: string
}

interface DeleteUserDialogProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  user: User | null
}

export default function DeleteUserDialog({ isOpen, onClose, onSuccess, user }: DeleteUserDialogProps) {
  const [isLoading, setIsLoading] = useState(false)

  const handleDelete = async () => {
    if (!user) return
    setIsLoading(true)
    try {
      /**
       * PERUBAHAN:
       * Sebelum: fetch(`/api/users/${user.id}`, { method: 'DELETE' })
       * Sesudah: apiClient.delete(`/api/users/${user.id}`) → FastAPI
       */
      const data = await apiClient.delete<{ message: string }>(`/api/users/${user.id}`)
      toast.success(data.message)
      onSuccess()
      onClose()
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete user')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="h-5 w-5" />
            Delete User
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this user? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        {user && (
          <div className="bg-gray-50 p-4 rounded-lg">
            <p className="font-medium text-gray-900">{user.fullName}</p>
            <p className="text-sm text-gray-500">{user.email}</p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>Cancel</Button>
          <Button variant="destructive" onClick={handleDelete} disabled={isLoading}>
            {isLoading ? 'Deleting...' : 'Delete User'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}