import { Person, PersonCreateInput, PersonListItem, PersonUpdateInput } from '@/types/persons';

// Note: server-side list fetching moved to lib/persons-server.ts to avoid next/headers in client bundles

// ---- Client-side helpers for CRUD (mirrors rfqs.ts style) ----
async function clientFetch(path: string, options?: RequestInit & { query?: Record<string, any> }) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';
  const url = new URL(path.startsWith('http') ? path : `${baseUrl}${path}`);

  if (options?.query) {
    Object.entries(options.query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const headers = new Headers(options?.headers);
  headers.set('Accept', 'application/json');

  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(url.toString(), {
    ...options,
    headers,
    credentials: 'include'
  });
}

export async function fetchPersonById(id: number): Promise<Person> {
  const resp = await clientFetch(`/api/persons/${id}/`);
  if (!resp.ok) throw new Error(`Backend error: ${resp.status}`);
  return resp.json();
}

export async function createPerson(payload: PersonCreateInput): Promise<Person> {
  const resp = await clientFetch('/api/persons/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(`Backend error: ${resp.status}`);
  return resp.json();
}

export async function updatePerson(id: number, payload: PersonUpdateInput): Promise<Person> {
  const resp = await clientFetch(`/api/persons/${id}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(`Backend error: ${resp.status}`);
  return resp.json();
}

