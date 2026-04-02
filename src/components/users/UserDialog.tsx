'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
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
  const [formData, setFormData] = useState<FormData>({ fullName: '', email: '', password: '', phoneNumber: '', role: 'USER' })

  useEffect(() => {
    if (!isOpen) return
    if (mode === 'create') {
      setFormData({ fullName: '', email: '', password: '', phoneNumber: '', role: 'USER' })
    } else if (user) {
      setFormData({ fullName: user.fullName || '', email: user.email || '', password: '', phoneNumber: user.phoneNumber || '', role: user.role || 'USER' })
    }
  }, [isOpen, mode, user])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const submitData: Record<string, unknown> = { fullName: formData.fullName, email: formData.email, phoneNumber: formData.phoneNumber, role: formData.role }
      if (mode === 'create' || formData.password.trim()) submitData.password = formData.password

      /**
       * PERUBAHAN:
       * Sebelum: fetch('/api/users', { method: 'POST', ... })
       * Sesudah: apiClient.post/put('/api/users', ...) → FastAPI
       */
      let data: any
      if (mode === 'create') {
        data = await apiClient.post('/api/users', submitData)
      } else {
        data = await apiClient.put(`/api/users/${user?.id}`, submitData)
      }

      toast.success(data.message || `User ${mode === 'create' ? 'created' : 'updated'} successfully`)
      onSuccess()
      onClose()
      setFormData({ fullName: '', email: '', password: '', phoneNumber: '', role: 'USER' })
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Failed to save user')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    setFormData({ fullName: '', email: '', password: '', phoneNumber: '', role: 'USER' })
    onClose()
  }

  const getTitle = () => {
    if (mode === 'create') return 'Add New User'
    if (mode === 'edit') return `Edit User - ${user?.fullName}`
    return `User Details - ${user?.fullName}`
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>{getTitle()}</DialogTitle></DialogHeader>

        {mode === 'view' ? (
          <div className="space-y-4">
            {[
              { label: 'Full Name', value: user?.fullName },
              { label: 'Email', value: user?.email },
              { label: 'Phone Number', value: user?.phoneNumber },
            ].map(({ label, value }) => (
              <div key={label}>
                <Label className="text-sm font-medium text-gray-600">{label}</Label>
                <p className="mt-1 text-sm text-gray-900">{value}</p>
              </div>
            ))}
            <div>
              <Label className="text-sm font-medium text-gray-600">Role</Label>
              <div className="mt-1"><Badge variant={user?.role === 'ADMIN' ? 'default' : 'secondary'}>{user?.role}</Badge></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label className="text-sm font-medium text-gray-600">Created</Label><p className="mt-1 text-xs text-gray-500">{user?.createdAt}</p></div>
              <div><Label className="text-sm font-medium text-gray-600">Updated</Label><p className="mt-1 text-xs text-gray-500">{user?.updatedAt}</p></div>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="fullName">Full Name *</Label>
              <Input id="fullName" value={formData.fullName} onChange={e => setFormData(p => ({ ...p, fullName: e.target.value }))} placeholder="Enter full name" required autoComplete="name" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email *</Label>
              <Input id="email" type="email" value={formData.email} onChange={e => setFormData(p => ({ ...p, email: e.target.value }))} placeholder="Enter email address" required autoComplete="email" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password {mode === 'create' ? '*' : '(leave blank to keep current)'}</Label>
              <Input id="password" type="password" value={formData.password} onChange={e => setFormData(p => ({ ...p, password: e.target.value }))} placeholder={mode === 'create' ? 'Enter password' : 'Enter new password'} required={mode === 'create'} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phoneNumber">Phone Number *</Label>
              <Input id="phoneNumber" value={formData.phoneNumber} onChange={e => setFormData(p => ({ ...p, phoneNumber: e.target.value }))} placeholder="Enter phone number" required autoComplete="tel" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Role *</Label>
              <Select value={formData.role} onValueChange={(v: 'USER' | 'ADMIN') => setFormData(p => ({ ...p, role: v }))}>
                <SelectTrigger><SelectValue placeholder="Select role" /></SelectTrigger>
                <SelectContent><SelectItem value="USER">User</SelectItem><SelectItem value="ADMIN">Admin</SelectItem></SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleClose} disabled={isLoading}>Cancel</Button>
              <Button type="submit" disabled={isLoading} className="bg-green-600 hover:bg-green-700 text-white">
                {isLoading ? (<><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />Saving...</>) : (mode === 'create' ? 'Create User' : 'Update User')}
              </Button>
            </DialogFooter>
          </form>
        )}

        {mode === 'view' && <DialogFooter><Button onClick={handleClose} className="bg-blue-600 hover:bg-blue-700 text-white">Close</Button></DialogFooter>}
      </DialogContent>
    </Dialog>
  )
}