import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Пути, которые не требуют аутентификации
  const publicPaths = ['/login', '/register', '/api', '/_next', '/favicon.ico']
  
  const isPublicPath = publicPaths.some(path => pathname.startsWith(path))
  
  if (isPublicPath) {
    return NextResponse.next()
  }

  // Проверяем наличие токена в cookies или localStorage
  // Поскольку в middleware нет доступа к localStorage, проверяем cookies
  const accessToken = request.cookies.get('auth.access_token')?.value
  
  if (!accessToken) {
    // Если нет токена, перенаправляем на страницу входа
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|login|register).*)']
}
