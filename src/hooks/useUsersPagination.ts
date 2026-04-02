'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/lib/api-client'

export interface User {
  id: string
  fullName: string
  email: string
  phoneNumber: string
  role: 'USER' | 'ADMIN'
  createdAt: string
  updatedAt: string
}

interface PaginationResponse {
  items: User[]
  nextCursor: string | null
  hasMore: boolean
  pagination: {
    limit: number
    total: number
    sortOrder: 'asc' | 'desc'
    filters: { role: string | null; search: string | null }
  }
}

type SortOrder = 'asc' | 'desc'

export function useUsersPagination(opts?: { enabled?: boolean }) {
  const enabled = opts?.enabled ?? true

  const [limit, setLimit] = useState(10)
  const [role, setRole] = useState('')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<SortOrder>('desc')
  const [users, setUsers] = useState<User[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const params = useMemo(() => ({ limit, role, search, sort }), [limit, role, search, sort])

  const buildUrl = useCallback((cursor?: string | null) => {
    const q = new URLSearchParams()
    if (cursor) q.append('cursor', cursor)
    q.append('limit', String(limit))
    if (role) q.append('role', role)
    if (search) q.append('search', search)
    q.append('sort', sort)
    return `/api/users?${q.toString()}`
  }, [limit, role, search, sort])

  const fetchUsers = useCallback(async (cursor?: string | null, reset = false) => {
    if (!enabled) return
    setIsLoading(true)
    setError(null)
    try {
      // PERUBAHAN: pakai apiClient bukan fetch() langsung
      // apiClient otomatis kirim JWT token ke FastAPI
      const data = await apiClient.get<PaginationResponse>(buildUrl(cursor))
      setUsers(prev => reset ? data.items : [...prev, ...data.items])
      setNextCursor(data.nextCursor)
      setHasMore(data.hasMore)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [buildUrl, enabled])

  const resetAndLoad = useCallback(() => {
    setUsers([])
    setNextCursor(null)
    setHasMore(true)
    setError(null)
    fetchUsers(null, true)
  }, [fetchUsers])

  useEffect(() => { resetAndLoad() }, [resetAndLoad, params])

  const loadMore = useCallback(() => {
    if (nextCursor && hasMore && !isLoading) fetchUsers(nextCursor, false)
  }, [nextCursor, hasMore, isLoading, fetchUsers])

  const removeFromList = useCallback((id: string) => {
    setUsers(prev => prev.filter(u => u.id !== id))
  }, [])

  return {
    users, isLoading, error, hasMore, nextCursor,
    limit, setLimit, role, setRole, search, setSearch, sort, setSort,
    loadMore, resetAndLoad, removeFromList
  }
}