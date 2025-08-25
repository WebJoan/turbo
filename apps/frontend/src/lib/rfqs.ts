import { RFQ, RFQCreateInput, RFQItemQuotationsResponse, RFQItemCreateInput } from '@/types/rfqs';

type ListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: RFQ[];
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

export async function fetchRFQsFromBackend(params: {
  page: number;
  perPage: number;
  search?: string;
  number?: string;
  company_name?: string;
  status?: string;
  priority?: string;
}): Promise<{ items: RFQ[]; total: number }> {
  const resp = await clientFetch('/api/rfqs/', {
    query: {
      page: params.page,
      page_size: params.perPage,
      search: params.search || undefined,
      number: params.number || undefined,
      company_name: params.company_name || undefined,
      status: params.status || undefined,
      priority: params.priority || undefined
    }
  });
  
  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
  
  const data: ListResponse = await resp.json();
  return { items: data.results, total: data.count };
}

export async function fetchRFQById(id: number): Promise<RFQ> {
  const resp = await clientFetch(`/api/rfqs/${id}/`);
  
  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
  
  return resp.json();
}

export async function createRFQ(data: RFQCreateInput): Promise<RFQ> {
  // Шаг 1: создаём RFQ и строки (JSON без файлов)
  const { items, ...rest } = data;
  const itemsWithoutFiles: Omit<RFQItemCreateInput, 'files'>[] | undefined = items?.map(({ files, ...i }) => i);

  const resp = await clientFetch('/api/rfqs/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ...rest, items: itemsWithoutFiles }),
  });

  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }

  const created: RFQ = await resp.json();

  // Шаг 2: если есть файлы, загружаем их для каждой строки в отдельный endpoint
  if (items && items.length > 0) {
    const uploadPromises: Promise<any>[] = [];
    for (const createdItem of created.items) {
      const original = items.find((i) => i.line_number === createdItem.line_number);
      if (!original || !original.files || original.files.length === 0) continue;

      const form = new FormData();
      for (const f of original.files) {
        form.append('files', f);
      }
      // Можно передать общий тип/описание при необходимости
      // form.append('file_type', 'other');

      uploadPromises.push(
        fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://api:8000'}/api/rfq-items/${createdItem.id}/files/`, {
          method: 'POST',
          body: form,
          headers: (() => {
            const h = new Headers();
            h.set('Accept', 'application/json');
            if (typeof window !== 'undefined') {
              const token = localStorage.getItem('access_token');
              if (token) h.set('Authorization', `Bearer ${token}`);
            }
            return h;
          })(),
          credentials: 'include'
        })
      );
    }

    try {
      await Promise.all(uploadPromises);
    } catch (e) {
      console.error('Ошибка загрузки файлов RFQItem:', e);
      // Не прерываем общий процесс создания RFQ, но логируем
    }
  }

  // Возвращаем обновлённый RFQ с файламиможет потребоваться дополнительный GET, но пока вернём ответ создания
  return created;
}

export async function updateRFQ(id: number, data: Partial<RFQ>): Promise<RFQ> {
  const resp = await clientFetch(`/api/rfqs/${id}/`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
  
  return resp.json();
}

export async function deleteRFQ(id: number): Promise<void> {
  const resp = await clientFetch(`/api/rfqs/${id}/`, {
    method: 'DELETE',
  });
  
  if (!resp.ok) {
    throw new Error(`Backend error: ${resp.status}`);
  }
}

export async function fetchRFQItemQuotations(rfqItemId: number): Promise<RFQItemQuotationsResponse> {
  console.log(`Запрос предложений для RFQ Item ID: ${rfqItemId}`);
  
  const resp = await clientFetch(`/api/rfq-items/${rfqItemId}/quotations/`);
  
  if (!resp.ok) {
    const errorText = await resp.text();
    console.error(`Backend error ${resp.status} for RFQItem ${rfqItemId}:`, errorText);
    throw new Error(`Backend error: ${resp.status}`);
  }
  
  const data = await resp.json();
  console.log(`Получены данные для RFQItem ${rfqItemId}:`, data);
  
  return data;
}
