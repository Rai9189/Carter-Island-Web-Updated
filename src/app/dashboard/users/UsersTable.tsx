'use client'

import type { User } from '@/hooks/useUsersPagination'

function Avatar({ name }: { name: string }) {
  const initials = (name || '?').split(' ').map(n => n[0] ?? '').join('').slice(0, 2).toUpperCase() || '?'
  return (
    <div className="w-9 h-9 rounded-full bg-gray-800 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
      {initials}
    </div>
  )
}

function fmtDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleDateString('id-ID', { year: 'numeric', month: '2-digit', day: '2-digit' })
      .split('/').reverse().join('-')
  } catch { return dateStr }
}

export function UsersTable(props: {
  users: User[]
  currentUserId: string
  onView: (u: User) => void
  onEdit: (u: User) => void
  onDelete: (u: User) => void
}) {
  const { users, currentUserId, onView, onEdit, onDelete } = props

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-100">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-100">
            {['NAMA', 'EMAIL', 'NO. TELEPON', 'ROLE', 'DIBUAT', 'ACTIONS'].map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-400 tracking-wider whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {users.map(u => (
            <tr key={u.id} className="bg-white hover:bg-gray-50 transition-colors">
              {/* Nama + avatar */}
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <Avatar name={u.fullName} />
                  <span className="font-medium text-gray-800 whitespace-nowrap">{u.fullName}</span>
                </div>
              </td>

              {/* Email */}
              <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{u.email}</td>

              {/* Phone */}
              <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{u.phoneNumber || '—'}</td>

              {/* Role badge */}
              <td className="px-4 py-3">
                <span className={`text-xs font-bold px-3 py-1 rounded-lg ${u.role === 'ADMIN' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 border border-gray-200'}`}>
                  {u.role}
                </span>
              </td>

              {/* Dibuat */}
              <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmtDate(u.createdAt)}</td>

              {/* Actions */}
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onView(u)}
                    className="flex items-center gap-1 px-3 py-1.5 border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-medium rounded-lg transition-colors"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    View
                  </button>
                  <button
                    onClick={() => onEdit(u)}
                    className="flex items-center gap-1 px-3 py-1.5 border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-medium rounded-lg transition-colors"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Edit
                  </button>
                  <button
                    onClick={() => onDelete(u)}
                    disabled={u.id === currentUserId}
                    className="flex items-center gap-1 px-3 py-1.5 bg-red-50 hover:bg-red-100 disabled:opacity-40 disabled:cursor-not-allowed text-red-600 text-xs font-medium rounded-lg border border-red-100 transition-colors"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Del
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}