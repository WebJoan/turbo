import { backendServerFetch } from '@/lib/backend-server';
import { CompanyListItem } from '@/types/companies';

type CompaniesListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Array<{
    id: number;
    ext_id: string;
    name: string;
    short_name?: string | null;
    inn?: string | null;
  }>;
};

export async function fetchCompaniesFromBackend(params: {
  page: number;
  perPage: number;
  search?: string;
}): Promise<{ items: CompanyListItem[]; total: number }> {
  const resp = await backendServerFetch('/api/companies/', {
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
  const data: CompaniesListResponse = await resp.json();
  const items: CompanyListItem[] = data.results.map((c) => ({
    id: c.id,
    ext_id: c.ext_id,
    name: c.name,
    short_name: c.short_name ?? null,
    inn: c.inn ?? null
  }));
  return { items, total: data.count };
}


