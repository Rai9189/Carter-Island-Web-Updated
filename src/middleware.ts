/**
 * Next.js Middleware — proteksi route tanpa NextAuth.
 *
 * Menggantikan: middleware NextAuth yang cek session server-side
 * Sekarang: cek JWT token dari cookie yang di-set saat login
 *
 * Cara kerja:
 * 1. Request masuk ke halaman /dashboard/*
 * 2. Middleware cek cookie 'access_token'
 * 3. Kalau tidak ada → redirect ke /auth/login
 * 4. Kalau ada → lanjut ke halaman
 *
 * Validasi token dilakukan di client-side via authHelper.verifySession()
 * saat komponen pertama kali mount.
 */
import { NextRequest, NextResponse } from 'next/server'

// Route yang butuh login
const PROTECTED_ROUTES = ['/dashboard']

// Route yang hanya bisa diakses saat belum login
const AUTH_ROUTES = ['/auth/login', '/auth/register']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Cek token dari cookie (di-set saat login via authHelper)
  const token = request.cookies.get('access_token')?.value

  // Kalau akses protected route tanpa token → redirect ke login
  const isProtected = PROTECTED_ROUTES.some((route) =>
    pathname.startsWith(route)
  )
  if (isProtected && !token) {
    const loginUrl = new URL('/auth/login', request.url)
    loginUrl.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Kalau sudah login dan akses halaman auth → redirect ke dashboard
  const isAuthRoute = AUTH_ROUTES.some((route) => pathname.startsWith(route))
  if (isAuthRoute && token) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/auth/login',
    '/auth/register',
  ],
}