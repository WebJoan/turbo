export interface ProductSubgroup {
  id: number;
  ext_id: string;
  name: string;
  group_name: string | null;
  display_name: string;
}

export interface Brand {
  id: number;
  ext_id: string;
  name: string;
  product_manager: string | null;
}

// Client-side функция для автокомплита подгрупп
export async function fetchSubgroupsAutocomplete(query: string = '', limit: number = 20): Promise<ProductSubgroup[]> {
  console.log('fetchSubgroupsAutocomplete called with:', { query, limit });
  
  // Создаем URL с query параметрами
  const url = new URL('/api/product-subgroups/autocomplete/', window.location.origin);
  if (query) url.searchParams.set('q', query);
  url.searchParams.set('limit', limit.toString());
  
  const resp = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include' // Включаем cookies для аутентификации
  });
  
  console.log('Response status:', resp.status);
  console.log('Response URL:', resp.url);
  
  if (!resp.ok) {
    const errorText = await resp.text().catch(() => 'Неизвестная ошибка');
    console.error('API error response:', errorText);
    throw new Error(`Ошибка при загрузке подгрупп: ${resp.status} - ${errorText}`);
  }
  
  const data: ProductSubgroup[] = await resp.json();
  console.log('Received data:', data);
  return data;
}

// Client-side функция для автокомплита брендов
export async function fetchBrandsAutocomplete(query: string = '', limit: number = 20): Promise<Brand[]> {
  console.log('fetchBrandsAutocomplete called with:', { query, limit });
  
  // Создаем URL с query параметрами
  const url = new URL('/api/brands/autocomplete/', window.location.origin);
  if (query) url.searchParams.set('q', query);
  url.searchParams.set('limit', limit.toString());
  
  const resp = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include' // Включаем cookies для аутентификации
  });
  
  console.log('Response status:', resp.status);
  console.log('Response URL:', resp.url);
  
  if (!resp.ok) {
    const errorText = await resp.text().catch(() => 'Неизвестная ошибка');
    console.error('API error response:', errorText);
    throw new Error(`Ошибка при загрузке брендов: ${resp.status} - ${errorText}`);
  }
  
  const data: Brand[] = await resp.json();
  console.log('Received brands data:', data);
  return data;
}

// Client-side функция для получения всех названий брендов
export async function fetchAllBrandNames(): Promise<string[]> {
  const resp = await fetch('/api/brands/get_all_names/', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include'
  });
  
  if (!resp.ok) {
    throw new Error(`Ошибка при загрузке названий брендов: ${resp.status}`);
  }
  
  return await resp.json();
}

// Client-side функция для экспорта описаний товаров с новыми фильтрами
export async function exportProductDescriptions(
  typecode?: string, 
  isAsync: boolean = false, 
  subgroupIds?: string[], 
  brandNames?: string[],
  onlyTwoParams?: boolean,
  noDescription?: boolean
): Promise<Response> {
  const body: any = {
    async: isAsync
  };
  
  // Обратная совместимость с typecode
  if (typecode) {
    body.typecode = typecode;
  }
  
  // Новые параметры
  if (subgroupIds && subgroupIds.length > 0) {
    body.subgroup_ids = subgroupIds;
  }
  
  if (brandNames && brandNames.length > 0) {
    body.brand_names = brandNames;
  }
  
  if (onlyTwoParams) {
    body.only_two_params = onlyTwoParams;
  }
  
  if (noDescription) {
    body.no_description = noDescription;
  }
  
  const resp = await fetch('/api/products/export-descriptions/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(body)
  });
  
  return resp;
}

// Client-side функция для проверки статуса экспорта
export async function checkExportTaskStatus(taskId: string): Promise<Response> {
  const resp = await fetch(`/api/products/export-status/${taskId}/`, {
    method: 'GET',
    credentials: 'include'
  });
  return resp;
}
