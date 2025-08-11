import { ApiError } from '@/lib/types/api'
import type { AuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'
import { getApiClient } from './api'

function decodeToken(token: string): {
  token_type: string
  exp: number
  iat: number
  jti: string
  user_id: number
} {
  const base64Url = token.split('.')[1]
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
  const payload = Buffer.from(base64, 'base64').toString('utf8')
  return JSON.parse(payload)
}

const authOptions: AuthOptions = {
  session: {
    strategy: 'jwt'
  },
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: '/login'
  },
  callbacks: {
    session: async ({ session, token }) => {
      // Если нет необходимых полей токена, вернуть сессию как есть (гость)
      if (!('access' in token) || !('refresh' in token)) {
        return session
      }

      try {
        const access = decodeToken((token as any).access)
        const refresh = decodeToken((token as any).refresh)

        // Если оба токена протухли — сессии нет
        if (Date.now() / 1000 > access.exp && Date.now() / 1000 > refresh.exp) {
          return session
        }

        session.user = {
          id: access.user_id,
          username: (token as any).username
        } as any

        ;(session as any).refreshToken = (token as any).refresh
        ;(session as any).accessToken = (token as any).access

        return session
      } catch (_e) {
        return session
      }
    },
    jwt: async ({ token, user }) => {
      // На первичной авторизации кладём поля пользователя/токенов в JWT
      if (user && (user as any).username) {
        return { ...token, ...user }
      }

      // Если нет access токена, нечего обновлять
      if (!(token as any).access || !(token as any).refresh) {
        return token
      }

      // Обновление access токена по необходимости
      try {
        const accessPayload = decodeToken((token as any).access)
        if (Date.now() / 1000 > accessPayload.exp) {
          const apiClient = await getApiClient()
          const res = await apiClient.token.tokenRefreshCreate({
            refresh: (token as any).refresh
          } as any)
          ;(token as any).access = (res as any).access
        }
      } catch (_e) {
        // В случае ошибки оставляем токен как есть
      }

      return token
    }
  },
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        username: {
          label: 'Email',
          type: 'text'
        },
        password: { label: 'Password', type: 'password' }
      },
      async authorize(credentials, _req) {
        if (credentials === undefined) {
          return null
        }

        try {
          const apiClient = await getApiClient()
          const res = await apiClient.token.tokenCreate({
            username: credentials.username,
            password: credentials.password
          } as any)

          return {
            id: String(decodeToken(res.access).user_id),
            username: credentials.username,
            access: res.access,
            refresh: res.refresh
          }
        } catch (_error) {
          return null
        }
      }
    })
  ]
}

export { authOptions }
