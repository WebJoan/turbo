'use client';

import { useEffect, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent
} from '@/components/ui/chart';
import { SalesFilters, TimeSeriesData } from '@/types/sales';
import { fetchCustomerSalesTimeSeries } from '@/lib/sales';
import { Skeleton } from '@/components/ui/skeleton';

interface CustomerSalesChartProps {
  companyId?: number;
  companyName?: string;
  filters?: SalesFilters;
  chartType?: 'line' | 'area' | 'bar';
}

const chartConfig = {
  revenue: {
    label: 'Выручка',
    color: 'hsl(var(--chart-1))'
  },
  orders: {
    label: 'Количество заказов',
    color: 'hsl(var(--chart-2))'
  },
  average_check: {
    label: 'Средний чек',
    color: 'hsl(var(--chart-3))'
  }
} satisfies ChartConfig;

export function CustomerSalesChart({
  companyId,
  companyName,
  filters,
  chartType = 'area'
}: CustomerSalesChartProps) {
  const [data, setData] = useState<TimeSeriesData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchCustomerSalesTimeSeries(companyId, filters);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [companyId, filters]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[300px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Ошибка</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0
    }).format(value);
  };

  const title = companyName
    ? `Динамика продаж: ${companyName}`
    : 'Динамика продаж по клиентам';

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>
          Объем выручки, количество заказов и средний чек
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[400px]">
          {chartType === 'line' && (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="period"
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return date.toLocaleDateString('ru-RU', {
                    month: 'short',
                    day: 'numeric'
                  });
                }}
              />
              <YAxis
                yAxisId="left"
                tickFormatter={formatCurrency}
                label={{ value: 'Выручка', angle: -90, position: 'insideLeft' }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                label={{
                  value: 'Заказы',
                  angle: 90,
                  position: 'insideRight'
                }}
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    formatter={(value, name) => {
                      if (name === 'revenue' || name === 'average_check') {
                        return formatCurrency(Number(value));
                      }
                      return value;
                    }}
                  />
                }
              />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="revenue"
                stroke="var(--color-revenue)"
                name="Выручка"
                strokeWidth={2}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="orders"
                stroke="var(--color-orders)"
                name="Заказы"
                strokeWidth={2}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="average_check"
                stroke="var(--color-average_check)"
                name="Средний чек"
                strokeWidth={2}
                strokeDasharray="5 5"
              />
            </LineChart>
          )}

          {chartType === 'area' && (
            <AreaChart data={data}>
              <defs>
                <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-revenue)"
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-revenue)"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="period"
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return date.toLocaleDateString('ru-RU', {
                    month: 'short',
                    day: 'numeric'
                  });
                }}
              />
              <YAxis tickFormatter={formatCurrency} />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    formatter={(value) => formatCurrency(Number(value))}
                  />
                }
              />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="var(--color-revenue)"
                fillOpacity={1}
                fill="url(#colorRevenue)"
                name="Выручка"
              />
            </AreaChart>
          )}

          {chartType === 'bar' && (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="period"
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return date.toLocaleDateString('ru-RU', {
                    month: 'short',
                    day: 'numeric'
                  });
                }}
              />
              <YAxis
                yAxisId="left"
                tickFormatter={formatCurrency}
                label={{ value: 'Выручка', angle: -90, position: 'insideLeft' }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                label={{
                  value: 'Заказы',
                  angle: 90,
                  position: 'insideRight'
                }}
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    formatter={(value, name) => {
                      if (name === 'revenue' || name === 'average_check') {
                        return formatCurrency(Number(value));
                      }
                      return value;
                    }}
                  />
                }
              />
              <Legend />
              <Bar
                yAxisId="left"
                dataKey="revenue"
                fill="var(--color-revenue)"
                name="Выручка"
              />
              <Bar
                yAxisId="right"
                dataKey="orders"
                fill="var(--color-orders)"
                name="Заказы"
              />
            </BarChart>
          )}
        </ChartContainer>
      </CardContent>
    </Card>
  );
}

