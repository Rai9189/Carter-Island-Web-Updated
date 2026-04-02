// src/app/dashboard/users/FiltersBar.tsx
'use client'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Search as SearchIcon } from 'lucide-react'

export function FiltersBar(props: {
  limit: number; setLimit: (n: number) => void
  role: string; setRole: (v: string) => void
  search: string; setSearch: (v: string) => void
  sort: 'asc'|'desc'; setSort: (v: 'asc'|'desc') => void
  loadedCount: number; hasMore: boolean
}) {
  const { limit, setLimit, role, setRole, search, setSearch, sort, setSort, loadedCount, hasMore } = props
  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div className="text-sm text-muted-foreground">
          Loaded <span className="font-medium">{loadedCount}</span> users{hasMore ? ' (more available)' : ' — end of list'}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm">Rows per page</span>
          <Select value={String(limit)} onValueChange={v => setLimit(parseInt(v,10))}>
            <SelectTrigger className="h-8 w-[88px]"><SelectValue placeholder={limit} /></SelectTrigger>
            <SelectContent>
              {[5,10,20,30,50].map(sz => <SelectItem key={sz} value={String(sz)}>{sz}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 pr-4 py-2 w-full rounded-md border border-gray-300 bg-white focus:outline-none focus:ring-0 focus:border-blue-600 transition"
          />
        </div>

        <Select value={role || 'all'} onValueChange={v => setRole(v === 'all' ? '' : v)}>
          <SelectTrigger className="h-12w-[150px]"><SelectValue placeholder="All Roles" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Roles</SelectItem>
            <SelectItem value="USER">User</SelectItem>
            <SelectItem value="ADMIN">Admin</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sort} onValueChange={v => setSort(v as 'asc'|'desc')}>
          <SelectTrigger className="h-12w-[140px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">Newest First</SelectItem>
            <SelectItem value="asc">Oldest First</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </>
  )
}
