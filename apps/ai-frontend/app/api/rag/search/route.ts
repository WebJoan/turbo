import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const query = (searchParams.get('query') || '').trim()
  const limit = searchParams.get('limit') || '10'
  const semanticRatio = searchParams.get('semantic_ratio')
  const threshold = searchParams.get('threshold')

  if (!query) {
    return NextResponse.json({ query: '', products: [], total_found: 0 })
  }

  const baseUrl = process.env.API_URL || 'http://api:8000'
  const token = cookies().get('auth.access_token')?.value

  const backendUrl = new URL('/api/rag/search/', baseUrl)
  backendUrl.searchParams.set('query', query)
  backendUrl.searchParams.set('limit', String(limit))
  if (semanticRatio) backendUrl.searchParams.set('semantic_ratio', String(semanticRatio))
  if (threshold) backendUrl.searchParams.set('threshold', String(threshold))

  try {
    const res = await fetch(backendUrl.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: 'no-store',
    })

    const data = await res.json().catch(() => null)
    if (!res.ok) {
      return NextResponse.json({ error: data?.error || 'Ошибка поиска' }, { status: res.status })
    }

    return NextResponse.json(data)
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Ошибка сети' }, { status: 500 })
  }
}


