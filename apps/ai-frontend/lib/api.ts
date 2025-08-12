import { ApiClient } from '@/lib/types/api'
import { AuthService } from './auth'

export async function getApiClient() {
  const isBrowser = typeof window !== 'undefined'
  const baseUrl = isBrowser ? '' : process.env.API_URL ?? 'http://api:8000'
  
  const accessToken = AuthService.getAccessToken()
  
  return new ApiClient({
    BASE: baseUrl,
    HEADERS: {
      ...(accessToken && {
        Authorization: `Bearer ${accessToken}`
      })
    }
  })
}
