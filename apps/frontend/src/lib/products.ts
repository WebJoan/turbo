import { backendServerFetch } from '@/lib/backend-server';
import { ProductListItem } from '@/types/products';

type ListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Array<{
    id: number;
    ext_id: string;
    name: string;
    complex_name: string;
    brand_name?: string | null;
    group_name?: string | null;
    subgroup_name?: string | null;
    assigned_manager?: {
      id: number;
      username: string;
      first_name: string;
      last_name: string;
    } | null;
  }>;
};

export async function fetchProductsFromBackend(params: {
  page: number;
  perPage: number;
  search?: string;
}): Promise<{ items: ProductListItem[]; total: number }> {
  const resp = await backendServerFetch('/api/products/', {
    query: {
      page: params.page,
      page_size: params.perPage,
      search: params.search || undefined
    }
  });
  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
  const data: ListResponse = await resp.json();
  const items: ProductListItem[] = data.results.map((p) => ({
    id: p.id,
    ext_id: p.ext_id,
    name: p.name,
    complex_name: p.complex_name,
    brand_name: p.brand_name ?? null,
    group_name: p.group_name ?? null,
    subgroup_name: p.subgroup_name ?? null,
    assigned_manager: p.assigned_manager ?? null
  }));
  return { items, total: data.count };
}

export async function searchProducts(params: {
  q?: string;
  ext_id?: string;
  page: number;
  perPage: number;
}): Promise<{ items: ProductListItem[]; total: number }> {
  const queryParams: Record<string, any> = {
    page: params.page,
    page_size: params.perPage
  };
  
  // Если указан ext_id, используем его для точного поиска
  if (params.ext_id) {
    queryParams.ext_id = params.ext_id;
  } else if (params.q) {
    queryParams.q = params.q;
  }
  
  const resp = await backendServerFetch('/api/products/search/', {
    query: queryParams
  });
  
  if (!resp.ok) {
    throw new Error(`Search error: ${resp.status}`);
  }
  
  const data = await resp.json();
  const hits: any[] = data.results || [];
  const total: number = data.count ?? hits.length;
  const items: ProductListItem[] = hits.map((p) => ({
    id: p.id,
    ext_id: p.ext_id,
    name: p.name,
    complex_name: p.complex_name,
    brand_name: p.brand_name ?? null,
    group_name: p.group_name ?? null,
    subgroup_name: p.subgroup_name ?? null,
    assigned_manager: p.assigned_manager ?? null
  }));
  return { items, total };
}


