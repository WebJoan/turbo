import {
  Competitor,
  CompetitorProduct,
  CompetitorProductMatch,
  CompetitorPriceStockSnapshot,
  CompetitorsFilters,
  CompetitorProductsFilters,
} from '@/types/stock';

type FetchInit = RequestInit & { query?: Record<string, string | number | boolean | undefined | null> };

function getBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';
}

async function clientFetch(path: string, init?: FetchInit): Promise<Response> {
  const base = getBaseUrl();
  const url = new URL(path.startsWith('http') ? path : `${base}${path.startsWith('/') ? '' : '/'}${path}`);

  if (init?.query) {
    for (const [key, value] of Object.entries(init.query)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers = new Headers(init?.headers);
  headers.set('Accept', 'application/json');

  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  return fetch(url.toString(), {
    ...init,
    headers,
    credentials: 'include',
    cache: 'no-store'
  });
}

// === Client-side Stock API (safe for client components) ===

export async function fetchCompetitorProductsClient(params: CompetitorProductsFilters = {}): Promise<{
  items: CompetitorProduct[];
  total: number;
}> {
  const resp = await clientFetch('/api/competitor-products/', {
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

  const data = await resp.json();
  return {
    items: (data.results || []) as CompetitorProduct[],
    total: Number(data.count || 0),
  };
}

export async function createCompetitorProductMatchClient(
  data: Partial<Pick<CompetitorProductMatch, 'match_type' | 'confidence' | 'notes'>> & {
    competitor_product: number;
    product: number;
  }
): Promise<CompetitorProductMatch> {
  const resp = await clientFetch('/api/competitor-matches/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function updateCompetitorProductClient(
  id: number,
  data: Partial<Pick<CompetitorProduct, 'mapped_product' | 'ext_id' | 'part_number' | 'brand_name' | 'name' | 'tech_params'>>
): Promise<CompetitorProduct> {
  const resp = await clientFetch(`/api/competitor-products/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  return resp.json();
}

export async function fetchPriceComparisonClient(productId: number): Promise<{
  our_product_id: number;
  our_product_name: string;
  our_current_price: number | null;
  our_price_history: any[];
  competitor_prices: CompetitorPriceStockSnapshot[];
  matches: CompetitorProductMatch[];
}> {
  const resp = await clientFetch(`/api/stock/price-comparison/${productId}/`);
  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchLatestCompetitorSnapshotsClient(params: { competitor_id?: number } = {}): Promise<CompetitorPriceStockSnapshot[]> {
  const resp = await clientFetch('/api/competitor-snapshots/latest/', {
    query: { competitor_id: params.competitor_id },
  });
  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
  return resp.json();
}

// === Utils (safe for client) ===

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
  } as const;
  return (statusMap as Record<string, string>)[status] || status;
}

export function formatMatchType(matchType: CompetitorProductMatch['match_type']): string {
  const typeMap = {
    exact: 'Точный',
    equivalent: 'Эквивалент',
    analog: 'Аналог',
    similar: 'Похожий',
  } as const;
  return (typeMap as Record<string, string>)[matchType] || matchType;
}


