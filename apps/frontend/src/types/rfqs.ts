// Модель валюты
export interface Currency {
  id: number;
  code: string;
  name: string;
  symbol: string;
  exchange_rate_to_rub: string;
  is_active: boolean;
  updated_at: string;
}

// Файл, прикреплённый к строке RFQ
export interface RFQItemFile {
  id: number;
  file: string; // URL
  file_type: 'photo' | 'datasheet' | 'specification' | 'drawing' | 'other';
  description: string;
  uploaded_at: string;
}

// Модель строки RFQ
export interface RFQItem {
  id: number;
  ext_id: string;
  line_number: number;
  product: number | null;
  // Внешний ID продукта из базы (Product.ext_id), если выбран товар из базы
  product_ext_id?: string | null;
  product_name: string;
  manufacturer: string;
  part_number: string;
  quantity: number;
  unit: string;
  specifications: string;
  comments: string;
  is_new_product: boolean;
  created_at: string;
  // Есть ли хотя бы одно предложение от product/purchaser по этой строке
  has_quotations?: boolean;
  files?: RFQItemFile[];
}

// Модель RFQ
export interface RFQ {
  id: number;
  ext_id: string;
  number: string;
  company: number;
  company_name: string;
  contact_person: number | null;
  sales_manager: number | null;
  sales_manager_username: string;
  status: 'draft' | 'submitted' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  description: string;
  deadline: string | null;
  delivery_address: string;
  payment_terms: string;
  delivery_terms: string;
  notes: string;
  created_at: string;
  updated_at: string;
  quotations_count: number;
  items: RFQItem[];
}

// Модель для создания RFQ
export interface RFQCreateInput {
  partnumber?: string;
  brand?: string;
  qty?: number;
  target_price?: number | null;
  items?: RFQItemCreateInput[];
  company_id?: number;
  description?: string;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  deadline?: string | null;
  delivery_address?: string;
  payment_terms?: string;
  delivery_terms?: string;
  notes?: string;
  contact_person_id?: number;
}

// Модель для создания строки RFQ
export interface RFQItemCreateInput {
  product?: number;
  product_name?: string;
  manufacturer?: string;
  part_number?: string;
  quantity: number;
  unit?: string;
  specifications?: string;
  comments?: string;
  is_new_product?: boolean;
  line_number?: number;
  // список файлов для загрузки при создании (используется на клиенте)
  files?: File[];
}

// Модель для строки предложения 
export interface QuotationItem {
  id: number;
  product: number | null;
  product_name: string | null;
  proposed_product_name: string;
  proposed_manufacturer: string;
  proposed_part_number: string;
  quantity: number;
  unit_cost_price: string;
  cost_markup_percent: string;
  unit_price: string;
  total_price: string;
  delivery_time: string;
  notes: string;
  // Файлы, прикреплённые к строке предложения
  files?: RFQItemFile[];
}

// Модель предложения
export interface Quotation {
  id: number;
  number: string;
  title: string;
  product_manager: number | null;
  product_manager_username: string;
  status: 'draft' | 'submitted' | 'accepted' | 'rejected' | 'expired';
  currency: number;
  currency_code: string;
  currency_symbol: string;
  description: string;
  valid_until: string | null;
  delivery_time: string;
  payment_terms: string;
  delivery_terms: string;
  notes: string;
  total_amount: string;
  created_at: string;
  updated_at: string;
  items: QuotationItem[];
}

// Модель ответа API для предложений по RFQItem
export interface RFQItemQuotationsResponse {
  rfq_item_id: number;
  quotations: {
    quotation: Quotation;
    quotation_item: QuotationItem;
  }[];
}

export interface LastPriceEntry {
  price: string;
  currency: string;
  invoice_date: string | null;
  invoice_number: string;
}

export interface RFQItemLastPrices {
  rfq_item_id: number;
  last_price_for_company: LastPriceEntry | null;
  last_price_any: LastPriceEntry | null;
}

export interface CreateQuotationInput {
  title?: string;
  quantity?: number;
  unit_cost_price: number | string;
  cost_expense_percent?: number | string;
  cost_markup_percent?: number | string;
  delivery_time?: string;
  payment_terms?: string;
  delivery_terms?: string;
  notes?: string;
  currency_id?: number;
  proposed_product_name?: string;
  proposed_manufacturer?: string;
  proposed_part_number?: string;
}
