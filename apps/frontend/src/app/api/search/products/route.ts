import { NextRequest } from 'next/server';
import { backendFetch } from '@/lib/backend';

// Proxy Meilisearch search for products. The backend indexes products to index "products" and secures MS key server-side.
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get('q') ?? '';
  const page = Number(searchParams.get('page') ?? '1');
  const perPage = Number(searchParams.get('perPage') ?? '10');

  // We will call a backend helper endpoint if exists or fallback to direct search proxy if provided there.
  // Prefer backend to perform MS query to avoid exposing keys.
  const resp = await backendFetch('/api/products', {
    // If "search" param present, DRF filter will perform LIKE search; but we want Meilisearch quality.
    // For now, we leverage a dedicated backend endpoint if present in future. As a fallback, use search to narrow results.
    query: {
      page,
      page_size: perPage,
      search: q || undefined
    }
  });

  const data = await resp.json();
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}


