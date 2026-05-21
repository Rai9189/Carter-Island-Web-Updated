'use client'

export function FiltersBar(props: {
  limit: number; setLimit: (n: number) => void
  role: string; setRole: (v: string) => void
  search: string; setSearch: (v: string) => void
  sort: 'asc' | 'desc'; setSort: (v: 'asc' | 'desc') => void
  loadedCount: number; hasMore: boolean
  onAddUser: () => void
}) {
  const { role, setRole, search, setSearch, sort, setSort, loadedCount, hasMore, onAddUser } = props

  return (
    <div className="flex flex-wrap items-center gap-3 mb-5">
      {/* Search */}
      <div className="relative flex-1 min-w-48">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Cari nama atau email..."
          className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 bg-white transition-colors"
        />
      </div>

      {/* Role filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">Role:</span>
        <select
          value={role || 'all'}
          onChange={e => setRole(e.target.value === 'all' ? '' : e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-blue-400 cursor-pointer"
        >
          <option value="all">Semua Role</option>
          <option value="ADMIN">Admin</option>
          <option value="USER">User</option>
        </select>
      </div>

      {/* Sort */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">Urutkan:</span>
        <select
          value={sort}
          onChange={e => setSort(e.target.value as 'asc' | 'desc')}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-blue-400 cursor-pointer"
        >
          <option value="desc">Terbaru</option>
          <option value="asc">Terlama</option>
        </select>
      </div>

      {/* Count */}
      <span className="text-sm text-gray-400 ml-auto">
        {loadedCount} pengguna ditemukan{hasMore ? ' (ada lebih)' : ''}
      </span>

      {/* Add button */}
      <button
        onClick={onAddUser}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
      >
        <span className="text-base leading-none">+</span>
        Add New User
      </button>
    </div>
  )
}