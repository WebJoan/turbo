// API клиенты для работы с данными о продажах

import {
  SalesFilters,
  SalesSummary,
  TimeSeriesData,
  Invoice,
  InvoiceLine,
  TopItem
} from '@/types/sales';

type FetchInit = RequestInit & {
  query?: Record<string, string | number | undefined | null>;
};

function getBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';
}

async function clientFetch(
  path: string,
  init?: FetchInit
): Promise<Response> {
  const base = getBaseUrl();
  const url = new URL(
    path.startsWith('http')
      ? path
      : `${base}${path.startsWith('/') ? '' : '/'}${path}`
  );

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

// === Получение общей статистики ===

export async function fetchSalesSummary(
  filters?: SalesFilters
): Promise<SalesSummary> {
  const response = await clientFetch('/api/sales/summary/', {
    query: filters as Record<string, string | number | undefined | null>
  });

  if (!response.ok) {
    throw new Error('Failed to fetch sales summary');
  }

  return response.json();
}

// === Динамика продаж по клиентам ===

export async function fetchCustomerSalesTimeSeries(
  companyId?: number,
  filters?: SalesFilters
): Promise<TimeSeriesData[]> {
  const query = {
    ...filters,
    company_id: companyId
  } as Record<string, string | number | undefined | null>;

  const response = await clientFetch('/api/sales/analytics/customers/timeseries/', {
    query
  });

  if (!response.ok) {
    throw new Error('Failed to fetch customer sales time series');
  }

  const data = await response.json();
  return data.results || data;
}

// === Топ клиентов ===

export async function fetchTopCustomers(
  filters?: SalesFilters,
  limit = 20
): Promise<TopItem[]> {
  const response = await clientFetch('/api/sales/analytics/customers/top/', {
    query: {
      ...filters,
      limit
    } as Record<string, string | number | undefined | null>
  });

  if (!response.ok) {
    throw new Error('Failed to fetch top customers');
  }

  const data = await response.json();
  return data.results || data;
}

// === Топ товаров ===

export async function fetchTopProducts(
  filters?: SalesFilters,
  limit = 20
): Promise<TopItem[]> {
  const response = await clientFetch('/api/sales/analytics/products/top/', {
    query: {
      ...filters,
      limit
    } as Record<string, string | number | undefined | null>
  });

  if (!response.ok) {
    throw new Error('Failed to fetch top products');
  }

  const data = await response.json();
  return data.results || data;
}

// === Динамика продаж по товарам ===

export async function fetchProductSalesTimeSeries(
  productId?: number,
  filters?: SalesFilters
): Promise<TimeSeriesData[]> {
  const query = {
    ...filters,
    product_id: productId
  } as Record<string, string | number | undefined | null>;

  const response = await clientFetch('/api/sales/analytics/products/timeseries/', {
    query
  });

  if (!response.ok) {
    throw new Error('Failed to fetch product sales time series');
  }

  const data = await response.json();
  return data.results || data;
}

// === Получение списка счетов ===

interface InvoiceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Invoice[];
}

export async function fetchInvoices(params: {
  page?: number;
  perPage?: number;
  filters?: SalesFilters;
}): Promise<{ items: Invoice[]; total: number }> {
  const { page = 1, perPage = 50, filters = {} } = params;

  const response = await clientFetch('/api/sales/invoices/', {
    query: {
      page,
      page_size: perPage,
      ...filters
    } as Record<string, string | number | undefined | null>
  });

  if (!response.ok) {
    throw new Error('Failed to fetch invoices');
  }

  const data: InvoiceListResponse = await response.json();

  return {
    items: data.results,
    total: data.count
  };
}

// === Получение деталей счета ===

export async function fetchInvoiceDetails(
  invoiceId: number
): Promise<Invoice & { lines: InvoiceLine[] }> {
  const response = await clientFetch(`/api/sales/invoices/${invoiceId}/`);

  if (!response.ok) {
    throw new Error('Failed to fetch invoice details');
  }

  return response.json();
}

