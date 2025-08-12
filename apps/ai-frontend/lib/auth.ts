interface User {
  id: number
  username: string
  first_name?: string
  last_name?: string
}

interface AuthTokens {
  access: string
  refresh: string
}

interface AuthUser {
  user: User
  tokens: AuthTokens
}

export class AuthService {
  private static readonly ACCESS_TOKEN_KEY = 'auth.access_token'
  private static readonly REFRESH_TOKEN_KEY = 'auth.refresh_token'
  private static readonly USER_KEY = 'auth.user'

  static isServer = typeof window === 'undefined'

  // Получение токена доступа
  static getAccessToken(): string | null {
    if (this.isServer) return null
    return localStorage.getItem(this.ACCESS_TOKEN_KEY)
  }

  // Получение refresh токена
  static getRefreshToken(): string | null {
    if (this.isServer) return null
    return localStorage.getItem(this.REFRESH_TOKEN_KEY)
  }

  // Получение пользователя
  static getUser(): User | null {
    if (this.isServer) return null
    const userData = localStorage.getItem(this.USER_KEY)
    return userData ? JSON.parse(userData) : null
  }

  // Сохранение данных аутентификации
  static saveAuth(authData: AuthUser): void {
    if (this.isServer) return

    localStorage.setItem(this.ACCESS_TOKEN_KEY, authData.tokens.access)
    localStorage.setItem(this.REFRESH_TOKEN_KEY, authData.tokens.refresh)
    localStorage.setItem(this.USER_KEY, JSON.stringify(authData.user))

    // Также сохраняем в cookies для middleware
    document.cookie = `auth.access_token=${authData.tokens.access}; path=/; SameSite=lax`
    document.cookie = `auth.refresh_token=${authData.tokens.refresh}; path=/; SameSite=lax`
  }

  // Очистка данных аутентификации
  static clearAuth(): void {
    if (this.isServer) return

    localStorage.removeItem(this.ACCESS_TOKEN_KEY)
    localStorage.removeItem(this.REFRESH_TOKEN_KEY)
    localStorage.removeItem(this.USER_KEY)

    // Очищаем cookies
    document.cookie = 'auth.access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT'
    document.cookie = 'auth.refresh_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT'
  }

  // Проверка авторизации
  static isAuthenticated(): boolean {
    return !!this.getAccessToken() && !!this.getUser()
  }

  // Декодирование JWT токена
  static decodeToken(token: string): any {
    try {
      const base64Url = token.split('.')[1]
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      )
      return JSON.parse(jsonPayload)
    } catch (error) {
      return null
    }
  }

  // Проверка истечения токена
  static isTokenExpired(token: string): boolean {
    const decoded = this.decodeToken(token)
    if (!decoded?.exp) return true
    
    return Date.now() >= decoded.exp * 1000
  }

  // Проверка, нужно ли обновить токен
  static shouldRefreshToken(): boolean {
    const accessToken = this.getAccessToken()
    if (!accessToken) return false
    
    return this.isTokenExpired(accessToken)
  }
}

// Типы для API запросов
export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  password_retype: string
}

export interface TokenRefreshRequest {
  refresh: string
}

// Экспортируем типы
export type { User, AuthTokens, AuthUser }
