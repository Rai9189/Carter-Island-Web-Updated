// src/app/dashboard/users/UsersTable.tsx
'use client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Edit, Eye, Trash2 } from 'lucide-react'
import type { User } from '@/hooks/useUsersPagination'

export function UsersTable(props: {
  users: User[]
  currentUserId: string
  onView: (u: User) => void
  onEdit: (u: User) => void
  onDelete: (u: User) => void
}) {
  const { users, currentUserId, onView, onEdit, onDelete } = props
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {['Name','Email','Phone','Role','Created','Actions'].map(h => (
              <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {users.map(u => (
            <tr key={u.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{u.fullName}</td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{u.email}</td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{u.phoneNumber}</td>
              <td className="px-6 py-4 whitespace-nowrap">
                <Badge
                  variant={u.role === 'ADMIN' ? 'default' : 'secondary'}
                  className={u.role === 'ADMIN' ? 'bg-red-100 text-red-800 hover:bg-red-200' : 'bg-green-100 text-green-800 hover:bg-green-200'}
                >
                  {u.role}
                </Badge>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{u.createdAt}</td>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                <Button size="sm" variant="outline" onClick={() => onView(u)} className="inline-flex items-center gap-1"><Eye className="h-3 w-3" />View</Button>
                <Button size="sm" onClick={() => onEdit(u)} className="inline-flex items-center gap-1"><Edit className="h-3 w-3" />Edit</Button>
                <Button size="sm" variant="destructive" onClick={() => onDelete(u)} disabled={u.id === currentUserId} className="inline-flex items-center gap-1">
                  <Trash2 className="h-3 w-3" />Delete
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
