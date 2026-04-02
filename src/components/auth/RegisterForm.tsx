'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { RegisterData } from '@/types/auth'
import { apiClient } from '@/lib/api-client'

export default function RegisterForm() {
  const [formData, setFormData] = useState<RegisterData>({
    fullName: '', email: '', password: '', phoneNumber: '', role: 'USER'
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      /**
       * PERUBAHAN:
       * Sebelum: fetch('/api/auth/register', { method: 'POST', ... })
       * Sesudah: apiClient.post('/api/auth/register', formData)
       *          → POST ke FastAPI port 8000
       */
      await apiClient.post('/api/auth/register', formData)
      setSuccess(true)
      setTimeout(() => router.push('/auth/login'), 2000)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  if (success) {
    return (
      <div className="max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-md">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-blue-600">Carter Island</h1>
          <p className="text-gray-600 mt-2">AUV Dashboard System</p>
          <div className="mt-4 p-3 bg-green-100 border border-green-400 text-green-700 rounded">
            Registration successful! Redirecting to login page...
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-md">
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold text-blue-600">Carter Island</h1>
        <p className="text-gray-600 mt-2">AUV Dashboard System</p>
        <h2 className="text-xl font-semibold mt-4">Create Account</h2>
      </div>

      {error && <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-4">
        {[
          { id: 'fullName', label: 'Full Name', type: 'text', placeholder: 'Enter your full name' },
          { id: 'email', label: 'Email Address', type: 'email', placeholder: 'Enter your email' },
          { id: 'password', label: 'Password', type: 'password', placeholder: 'Minimum 6 characters' },
          { id: 'phoneNumber', label: 'Phone Number', type: 'tel', placeholder: 'Enter your phone number' },
        ].map(({ id, label, type, placeholder }) => (
          <div key={id}>
            <label htmlFor={id} className="block text-sm font-medium text-gray-700">{label}</label>
            <input type={type} id={id} name={id} value={(formData as any)[id]} onChange={handleChange} required={id !== 'password' || true}
              minLength={id === 'password' ? 6 : undefined} placeholder={placeholder}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
        ))}

        <div>
          <label htmlFor="role" className="block text-sm font-medium text-gray-700">Role</label>
          <select id="role" name="role" value={formData.role} onChange={handleChange}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
            <option value="USER">User</option>
            <option value="ADMIN">Admin</option>
          </select>
        </div>

        <button type="submit" disabled={loading}
          className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed">
          {loading ? 'Creating Account...' : 'Create Account'}
        </button>
      </form>

      <div className="mt-4 text-center">
        <a href="/auth/login" className="text-sm text-blue-600 hover:text-blue-500">Already have an account? Sign in here</a>
      </div>
    </div>
  )
}