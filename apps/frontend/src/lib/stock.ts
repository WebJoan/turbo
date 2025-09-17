import { backendServerFetch } from '@/lib/backend-server';
import {
  Competitor,
  CompetitorProduct,
  CompetitorProductMatch,
  CompetitorPriceStockSnapshot,
  OurPriceHistory,
  PriceComparison,
  CompetitorsListResponse,
  CompetitorProductsListResponse,
  CompetitorProductMatchesListResponse,
  CompetitorPriceStockSnapshotsListResponse,
  OurPriceHistoryListResponse,
  CompetitorsFilters,
  CompetitorProductsFilters,
  CompetitorPriceStockSnapshotsFilters,
  OurPriceHistoryFilters,
} from '@/types/stock';

// === Competitors API ===

export async function fetchCompetitors(params: CompetitorsFilters = {}): Promise<{
  items: Competitor[];
  total: number;
}> {
  const resp = await backendServerFetch('/api/competitors/', {
    query: {
      page: params.page || 1,
      page_size: params.page_size || 20,
      name_contains: params.name_contains,
      is_active: params.is_active,
    },
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  const data: CompetitorsListResponse = await resp.json();
  return {
    items: data.results,
    total: data.count,
  };
}

export async function fetchCompetitor(id: number): Promise<Competitor> {
  const resp = await backendServerFetch(`/api/competitors/${id}/`);

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function createCompetitor(data: Omit<Competitor, 'id' | 'created_at' | 'updated_at'>): Promise<Competitor> {
  const resp = await backendServerFetch('/api/competitors/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function updateCompetitor(id: number, data: Partial<Competitor>): Promise<Competitor> {
  const resp = await backendServerFetch(`/api/competitors/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function deleteCompetitor(id: number): Promise<void> {
  const resp = await backendServerFetch(`/api/competitors/${id}/`, {
    method: 'DELETE',
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
}

// === Competitor Products API ===

export async function fetchCompetitorProducts(params: CompetitorProductsFilters = {}): Promise<{
  items: CompetitorProduct[];
  total: number;
}> {
  const resp = await backendServerFetch('/api/competitor-products/', {
    query: {
      page: params.page || 1,
      page_size: params.page_size || 20,
      competitor_id: params.competitor_id,
      part_number: params.part_number,
      brand_name: params.brand_name,
      has_mapping: params.has_mapping,
    },
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  const data: CompetitorProductsListResponse = await resp.json();
  return {
    items: data.results,
    total: data.count,
  };
}

export async function fetchCompetitorProduct(id: number): Promise<CompetitorProduct> {
  const resp = await backendServerFetch(`/api/competitor-products/${id}/`);

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function createCompetitorProduct(data: Omit<CompetitorProduct, 'id' | 'created_at' | 'updated_at'>): Promise<CompetitorProduct> {
  const resp = await backendServerFetch('/api/competitor-products/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function updateCompetitorProduct(id: number, data: Partial<CompetitorProduct>): Promise<CompetitorProduct> {
  const resp = await backendServerFetch(`/api/competitor-products/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function deleteCompetitorProduct(id: number): Promise<void> {
  const resp = await backendServerFetch(`/api/competitor-products/${id}/`, {
    method: 'DELETE',
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
}

// === Competitor Product Matches API ===

export async function fetchCompetitorProductMatches(params: { product_id?: number; page?: number; page_size?: number } = {}): Promise<{
  items: CompetitorProductMatch[];
  total: number;
}> {
  const resp = await backendServerFetch('/api/competitor-matches/', {
    query: {
      page: params.page || 1,
      page_size: params.page_size || 20,
      product_id: params.product_id,
    },
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  const data: CompetitorProductMatchesListResponse = await resp.json();
  return {
    items: data.results,
    total: data.count,
  };
}

export async function createCompetitorProductMatch(data: Omit<CompetitorProductMatch, 'id' | 'created_at' | 'updated_at'>): Promise<CompetitorProductMatch> {
  const resp = await backendServerFetch('/api/competitor-matches/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function updateCompetitorProductMatch(id: number, data: Partial<CompetitorProductMatch>): Promise<CompetitorProductMatch> {
  const resp = await backendServerFetch(`/api/competitor-matches/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function deleteCompetitorProductMatch(id: number): Promise<void> {
  const resp = await backendServerFetch(`/api/competitor-matches/${id}/`, {
    method: 'DELETE',
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
}

// === Competitor Price/Stock Snapshots API ===

export async function fetchCompetitorPriceStockSnapshots(params: CompetitorPriceStockSnapshotsFilters = {}): Promise<{
  items: CompetitorPriceStockSnapshot[];
  total: number;
}> {
  const resp = await backendServerFetch('/api/competitor-snapshots/', {
    query: {
      page: params.page || 1,
      page_size: params.page_size || 20,
      competitor_id: params.competitor_id,
      competitor_product_id: params.competitor_product_id,
      collected_after: params.collected_after,
      collected_before: params.collected_before,
      stock_status: params.stock_status,
      has_stock: params.has_stock,
    },
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  const data: CompetitorPriceStockSnapshotsListResponse = await resp.json();
  return {
    items: data.results,
    total: data.count,
  };
}

export async function fetchLatestCompetitorSnapshots(params: { competitor_id?: number } = {}): Promise<CompetitorPriceStockSnapshot[]> {
  const resp = await backendServerFetch('/api/competitor-snapshots/latest/', {
    query: {
      competitor_id: params.competitor_id,
    },
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function createCompetitorPriceStockSnapshot(data: Omit<CompetitorPriceStockSnapshot, 'id' | 'created_at' | 'updated_at' | 'competitor_name' | 'product_part_number'>): Promise<CompetitorPriceStockSnapshot> {
  const resp = await backendServerFetch('/api/competitor-snapshots/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

// === Our Price History API ===

export async function fetchOurPriceHistory(params: OurPriceHistoryFilters = {}): Promise<{
  items: OurPriceHistory[];
  total: number;
}> {
  const resp = await backendServerFetch('/api/our-price-history/', {
    query: {
      page: params.page || 1,
      page_size: params.page_size || 20,
      product_id: params.product_id,
      moment_after: params.moment_after,
      moment_before: params.moment_before,
    },
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  const data: OurPriceHistoryListResponse = await resp.json();
  return {
    items: data.results,
    total: data.count,
  };
}

export async function createOurPriceHistory(data: Omit<OurPriceHistory, 'id' | 'created_at' | 'updated_at' | 'product_name' | 'product_ext_id' | 'price_inc_vat'>): Promise<OurPriceHistory> {
  const resp = await backendServerFetch('/api/our-price-history/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

// === Price Comparison API ===

export async function fetchPriceComparison(productId: number): Promise<PriceComparison> {
  const resp = await backendServerFetch(`/api/stock/price-comparison/${productId}/`);

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

// === Import API ===

export async function importHistprice(): Promise<{ task_id: string }> {
  const resp = await backendServerFetch('/api/stock/import-histprice/', {
    method: 'POST',
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

// === Utility functions ===

export function formatPrice(price: number | null, currency: string = 'RUB'): string {
  if (price === null) return 'N/A';
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
  }).format(price);
}

export function formatStockStatus(status: CompetitorPriceStockSnapshot['stock_status']): string {
  const statusMap = {
    in_stock: 'В наличии',
    low_stock: 'Мало',
    out_of_stock: 'Нет в наличии',
    on_request: 'Под заказ',
  };
  return statusMap[status] || status;
}

export function formatMatchType(matchType: CompetitorProductMatch['match_type']): string {
  const typeMap = {
    exact: 'Точный',
    equivalent: 'Эквивалент',
    analog: 'Аналог',
    similar: 'Похожий',
  };
  return typeMap[matchType] || matchType;
}
