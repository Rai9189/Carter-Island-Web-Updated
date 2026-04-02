export interface User {
  id: string
  fullName: string
  email: string
  phoneNumber: string
  role: 'USER' | 'ADMIN'
}

export interface RegisterData {
  fullName: string
  email: string
  password: string
  phoneNumber: string
  role?: 'USER' | 'ADMIN'
}

export interface LoginData {
  email: string
  password: string
}