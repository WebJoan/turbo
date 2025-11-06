'use client';

import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { SalesFilters, SalesSummary } from '@/types/sales';
import { fetchSalesSummary } from '@/lib/sales';
import { Skeleton } from '@/components/ui/skeleton';
import {
  TrendingUpIcon,
  TrendingDownIcon,
  DollarSignIcon,
  ShoppingCartIcon,
  UsersIcon,
  ReceiptIcon
} from 'lucide-react';

interface SalesSummaryProps {
  filters?: SalesFilters;
}

export function SalesSummaryComponent({ filters }: SalesSummaryProps) {
  const [summary, setSummary] = useState<SalesSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchSalesSummary(filters);
        setSummary(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [filters]);

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-4" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-32" />
              <Skeleton className="mt-2 h-3 w-40" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error || !summary) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Ошибка</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive">
            {error || 'Не удалось загрузить сводку'}
          </p>
        </CardContent>
      </Card>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat('ru-RU').format(value);
  };

  const cards = [
    {
      title: 'Общая выручка',
      value: formatCurrency(summary.total_revenue),
      icon: DollarSignIcon,
      description: summary.growth_rate
        ? `${summary.growth_rate > 0 ? '+' : ''}${summary.growth_rate.toFixed(1)}% к предыдущему периоду`
        : 'За выбранный период'
    },
    {
      title: 'Всего заказов',
      value: formatNumber(summary.total_orders),
      icon: ShoppingCartIcon,
      description: 'Количество счетов на продажу'
    },
    {
      title: 'Уникальных клиентов',
      value: formatNumber(summary.total_customers),
      icon: UsersIcon,
      description: 'Совершивших покупки'
    },
    {
      title: 'Средний чек',
      value: formatCurrency(summary.average_check),
      icon: ReceiptIcon,
      description: 'Средняя сумма заказа'
    }
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, index) => {
        const Icon = card.icon;
        return (
          <Card key={index}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {card.title}
              </CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
              <p className="text-xs text-muted-foreground">
                {card.description}
              </p>
              {index === 0 && summary.growth_rate !== undefined && (
                <div className="mt-2 flex items-center text-xs">
                  {summary.growth_rate > 0 ? (
                    <>
                      <TrendingUpIcon className="mr-1 h-3 w-3 text-green-500" />
                      <span className="text-green-500">
                        Рост на {summary.growth_rate.toFixed(1)}%
                      </span>
                    </>
                  ) : summary.growth_rate < 0 ? (
                    <>
                      <TrendingDownIcon className="mr-1 h-3 w-3 text-red-500" />
                      <span className="text-red-500">
                        Снижение на {Math.abs(summary.growth_rate).toFixed(1)}%
                      </span>
                    </>
                  ) : (
                    <span className="text-muted-foreground">Без изменений</span>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

