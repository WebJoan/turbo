// Типы для работы с данными о продажах

export interface Invoice {
  id: number;
  ext_id: string;
  invoice_number: string;
  invoice_date: string;
  company: {
    id: number;
    name: string;
    short_name?: string;
    company_type: 'end_user' | 'reseller';
    is_partner: boolean;
  };
  invoice_type: 'purchase' | 'sale';
  sale_type?: 'stock' | 'order';
  currency: 'RUB' | 'USD' | 'CNY';
  total_amount?: number;
  created_at: string;
  updated_at: string;
}

export interface InvoiceLine {
  id: number;
  ext_id: string;
  invoice: number;
  product: {
    id: number;
    name: string;
    article?: string;
    brand?: {
      id: number;
      name: string;
    };
    subgroup?: {
      id: number;
      name: string;
    };
  };
  quantity: number;
  price: string;
  total_price: string;
  created_at: string;
  updated_at: string;
}

// Аналитика продаж по клиентам
export interface CustomerSalesAnalytics {
  company_id: number;
  company_name: string;
  company_type: 'end_user' | 'reseller';
  is_partner: boolean;
  period: string; // Дата в формате YYYY-MM-DD или YYYY-MM или YYYY
  total_revenue: number;
  order_count: number;
  average_check: number;
}

// Аналитика продаж по товарам
export interface ProductSalesAnalytics {
  product_id: number;
  product_name: string;
  product_article?: string;
  brand_name?: string;
  subgroup_name?: string;
  period: string;
  total_revenue: number;
  order_count: number;
  quantity_sold: number;
  average_price: number;
}

// Аналитика продаж по каналам
export interface ChannelSalesAnalytics {
  channel_type: 'vip' | 'regular'; // ВИП (партнеры) vs обычные
  customer_type: 'end_user' | 'reseller'; // Конечники vs перекупы
  period: string;
  total_revenue: number;
  order_count: number;
  customer_count: number;
  average_check: number;
}

// География продаж
export interface GeographySalesAnalytics {
  region?: string; // Регион
  city?: string; // Город
  district?: string; // Округ
  period: string;
  total_revenue: number;
  order_count: number;
  customer_count: number;
}

// Фильтры для запросов
export interface SalesFilters {
  date_from?: string;
  date_to?: string;
  period_type?: 'day' | 'week' | 'month' | 'year';
  company_id?: number;
  product_id?: number;
  channel_type?: 'vip' | 'regular';
  customer_type?: 'end_user' | 'reseller';
  region?: string;
  city?: string;
  currency?: 'RUB' | 'USD' | 'CNY';
  sale_type?: 'stock' | 'order';
}

// Агрегированная статистика
export interface SalesSummary {
  total_revenue: number;
  total_orders: number;
  total_customers: number;
  average_check: number;
  growth_rate?: number; // Процент роста по сравнению с предыдущим периодом
}

// Топ клиентов/товаров
export interface TopItem {
  id: number;
  name: string;
  total_revenue: number;
  order_count: number;
  percentage: number; // Процент от общей выручки
}

// Данные для графика динамики
export interface TimeSeriesData {
  period: string;
  revenue: number;
  orders: number;
  customers?: number;
  average_check: number;
}

