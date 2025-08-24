import { cookies } from 'next/headers';

export function getBackendBaseUrl(): string {
  return (
    process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://api:8000'
  );
}

type FetchInit = RequestInit & { query?: Record<string, string | number | undefined | null> };

export async function backendFetch(path: string, init?: FetchInit): Promise<Response> {
  const base = getBackendBaseUrl();
  const url = new URL(path.startsWith('http') ? path : `${base}${path.startsWith('/') ? '' : '/'}${path}`);

  if (init?.query) {
    for (const [key, value] of Object.entries(init.query)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const cookieStore = await cookies();
  const access = cookieStore.get('access_token')?.value;
  const refresh = cookieStore.get('refresh_token')?.value;

  const headers = new Headers(init?.headers);
  headers.set('Accept', 'application/json');
  if (access || refresh) {
    const cookieHeader: string[] = [];
    if (access) cookieHeader.push(`access_token=${access}`);
    if (refresh) cookieHeader.push(`refresh_token=${refresh}`);
    headers.set('Cookie', cookieHeader.join('; '));
  }

  return fetch(url.toString(), {
    ...init,
    headers,
    credentials: 'include',
    cache: 'no-store'
  });
}


