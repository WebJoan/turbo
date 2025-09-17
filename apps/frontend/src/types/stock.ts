export interface Competitor {
  id: number;
  name: string;
  site_url: string | null;
  b2b_site_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CompetitorProduct {
  id: number;
  competitor: Competitor;
  ext_id: string | null;
  part_number: string;
  brand_name: string | null;
  name: string | null;
  tech_params: Record<string, any> | null;
  mapped_product: number | null;
  mapped_product_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompetitorProductMatch {
  id: number;
  competitor_product: CompetitorProduct;
  product: number;
  product_name: string;
  product_ext_id: string;
  match_type: "exact" | "equivalent" | "analog" | "similar";
  confidence: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompetitorPriceStockSnapshot {
  id: number;
  competitor: Competitor;
  competitor_product: CompetitorProduct;
  competitor_name: string;
  product_part_number: string;
  collected_at: string;
  price_ex_vat: number | null;
  vat_rate: number | null;
  currency: string;
  stock_qty: number | null;
  stock_status: "in_stock" | "low_stock" | "out_of_stock" | "on_request";
  delivery_days_min: number | null;
  delivery_days_max: number | null;
  raw_payload: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface OurPriceHistory {
  id: number;
  product: number;
  product_name: string;
  product_ext_id: string;
  moment: string;
  price_ex_vat: number;
  vat_rate: number;
  price_inc_vat: number;
  created_at: string;
  updated_at: string;
}

export interface PriceComparison {
  our_product_id: number;
  our_product_name: string;
  our_current_price: number | null;
  our_price_history: OurPriceHistory[];
  competitor_prices: CompetitorPriceStockSnapshot[];
  matches: CompetitorProductMatch[];
}

// Типы для форм
export interface CompetitorFormData {
  name: string;
  site_url?: string;
  b2b_site_url?: string;
  is_active: boolean;
}

export interface CompetitorProductFormData {
  competitor: number;
  ext_id?: string;
  part_number: string;
  brand_name?: string;
  name?: string;
  tech_params?: Record<string, any>;
  mapped_product?: number;
}

export interface CompetitorProductMatchFormData {
  competitor_product: number;
  product: number;
  match_type: "exact" | "equivalent" | "analog" | "similar";
  confidence: number;
  notes?: string;
}

export interface CompetitorPriceStockSnapshotFormData {
  competitor: number;
  competitor_product: number;
  collected_at: string;
  price_ex_vat?: number;
  vat_rate?: number;
  currency: string;
  stock_qty?: number;
  stock_status: "in_stock" | "low_stock" | "out_of_stock" | "on_request";
  delivery_days_min?: number;
  delivery_days_max?: number;
  raw_payload?: Record<string, any>;
}

export interface OurPriceHistoryFormData {
  product: number;
  moment: string;
  price_ex_vat: number;
  vat_rate: number;
}

// Типы для API ответов
export interface CompetitorsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Competitor[];
}

export interface CompetitorProductsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CompetitorProduct[];
}

export interface CompetitorProductMatchesListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CompetitorProductMatch[];
}

export interface CompetitorPriceStockSnapshotsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CompetitorPriceStockSnapshot[];
}

export interface OurPriceHistoryListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: OurPriceHistory[];
}

// Типы для фильтров
export interface CompetitorsFilters {
  name_contains?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export interface CompetitorProductsFilters {
  competitor_id?: number;
  part_number?: string;
  brand_name?: string;
  has_mapping?: boolean;
  page?: number;
  page_size?: number;
}

export interface CompetitorPriceStockSnapshotsFilters {
  competitor_id?: number;
  competitor_product_id?: number;
  collected_after?: string;
  collected_before?: string;
  stock_status?: string;
  has_stock?: boolean;
  page?: number;
  page_size?: number;
}

export interface OurPriceHistoryFilters {
  product_id?: number;
  moment_after?: string;
  moment_before?: string;
  page?: number;
  page_size?: number;
}
