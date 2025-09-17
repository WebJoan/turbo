import { backendServerFetch } from '@/lib/backend-server';
import { PersonListItem } from '@/types/persons';

type PersonsListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Array<PersonListItem>;
};

export async function fetchPersonsFromBackend(params: {
  page: number;
  perPage: number;
  search?: string;
}): Promise<{ items: PersonListItem[]; total: number }> {
  const resp = await backendServerFetch('/api/persons/', {
    query: {
      page: params.page,
      page_size: params.perPage,
      search: params.search || undefined,
    },
  });
  if (!resp.ok) {
    if (resp.status === 404) {
      return { items: [], total: 0 };
    }
    throw new Error(`Backend error: ${resp.status}`);
  }
  const data: PersonsListResponse = await resp.json();
  return { items: data.results, total: data.count };
}


