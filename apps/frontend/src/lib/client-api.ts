import { CompanyListItem } from '@/types/companies';
import { PersonListItem } from '@/types/persons';

type ListResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

// Client-side fetch function
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
  
  // Get token from localStorage or cookies if available
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }
  
  return fetch(url.toString(), {
    ...options,
    headers,
    credentials: 'include'
  });
}

// Companies API
export async function fetchCompaniesFromClient(params: {
  page: number;
  perPage: number;
  search?: string;
}): Promise<{ items: CompanyListItem[]; total: number }> {
  const resp = await clientFetch('/api/companies/', {
    query: {
      page: params.page,
      page_size: params.perPage,
      search: params.search || undefined
    }
  });
  
  if (!resp.ok) {
    if (resp.status === 404) {
      return { items: [], total: 0 };
    }
    throw new Error(`Backend error: ${resp.status}`);
  }
  
  const data: ListResponse<any> = await resp.json();
  const items: CompanyListItem[] = data.results.map((c: any) => ({
    id: Number(c.id),
    ext_id: c.ext_id,
    name: c.name,
    short_name: c.short_name ?? null,
    inn: c.inn ?? null
  }));
  
  return { items, total: data.count };
}

// Persons API
export async function fetchPersonsFromClient(params: {
  page: number;
  perPage: number;
  search?: string;
}): Promise<{ items: PersonListItem[]; total: number }> {
  const resp = await clientFetch('/api/persons/', {
    query: {
      page: params.page,
      page_size: params.perPage,
      search: params.search || undefined
    }
  });
  
  if (!resp.ok) {
    if (resp.status === 404) {
      return { items: [], total: 0 };
    }
    throw new Error(`Backend error: ${resp.status}`);
  }
  
  const data: ListResponse<PersonListItem> = await resp.json();
  return { items: data.results, total: data.count };
}

// Single company by ID (for prefill)
export async function fetchCompanyByIdFromClient(id: number): Promise<CompanyListItem | null> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';
  const url = `${baseUrl}/api/companies/${id}/`;
  const headers = new Headers();
  headers.set('Accept', 'application/json');
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }
  const resp = await fetch(url, { headers, credentials: 'include' });
  if (!resp.ok) {
    if (resp.status === 404) return null;
    throw new Error(`Backend error: ${resp.status}`);
  }
  const c: any = await resp.json();
  return {
    id: Number(c.id),
    ext_id: c.ext_id,
    name: c.name,
    short_name: c.short_name ?? null,
    inn: c.inn ?? null,
  };
}

// Product types
export interface ProductListItem {
  id: number;
  ext_id: string;
  name: string;
  complex_name: string;
  group_name: string;
  subgroup_name: string;
  brand_name: string;
  assigned_manager?: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
  };
}

// Products API
export async function searchProductsFromClient(params: {
  search?: string;
  limit?: number;
}): Promise<{ items: ProductListItem[]; total: number }> {
  const resp = await clientFetch('/api/products/ms-search/', {
    query: {
      q: params.search || '',
      page: 1,
      page_size: params.limit || 10
    }
  });
  
  if (!resp.ok) {
    if (resp.status === 404) {
      return { items: [], total: 0 };
    }
    throw new Error(`Backend error: ${resp.status}`);
  }
  
  const data = await resp.json();
  return { items: data.results || [], total: data.count || 0 };
}
