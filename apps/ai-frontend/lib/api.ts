import { ApiClient } from '@/lib/types/api'
import type { Session } from 'next-auth'

export async function getApiClient(session?: Session | null) {
  const isBrowser = typeof window !== 'undefined'
  const baseUrl = isBrowser ? '' : process.env.API_URL ?? 'http://api:8000'
  return new ApiClient({
    BASE: baseUrl,
    HEADERS: {
      ...((session as any) && (session as any).accessToken && {
        Authorization: `Bearer ${(session as any).accessToken}`
      })
    }
  })
}
