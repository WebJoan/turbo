'use client';

import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, LabelList, XAxis, YAxis } from 'recharts';

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
import { Skeleton } from '@/components/ui/skeleton';
import { fetchTopCustomers } from '@/lib/sales';
import { SalesFilters, TopItem } from '@/types/sales';

interface TopCustomersChartProps {
    filters?: SalesFilters;
    limit?: number;
}

const chartConfig = {
    total_revenue: {
        label: 'Выручка',
        color: 'hsl(var(--chart-1))'
    }
} satisfies ChartConfig;

export function TopCustomersChart({
    filters,
    limit = 20
}: TopCustomersChartProps) {
    const [data, setData] = useState<TopItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let isMounted = true;

        const loadData = async () => {
            try {
                setLoading(true);
                setError(null);
                const result = await fetchTopCustomers(filters, limit);
                if (isMounted) {
                    setData(result);
                }
            } catch (err) {
                if (isMounted) {
                    setError(
                        err instanceof Error ? err.message : 'Ошибка загрузки данных'
                    );
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        loadData();

        return () => {
            isMounted = false;
        };
    }, [filters, limit]);

    const formatCurrency = (value: number) =>
        new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            maximumFractionDigits: 0
        }).format(value);

    const chartData = useMemo(
        () =>
            data.map((item) => ({
                ...item,
                total_revenue: Number(item.total_revenue),
                percentage: Number(item.percentage)
            })),
        [data]
    );

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <Skeleton className="h-6 w-52" />
                    <Skeleton className="h-4 w-64" />
                </CardHeader>
                <CardContent>
                    <Skeleton className="h-[520px] w-full" />
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

    return (
        <Card>
            <CardHeader>
                <CardTitle>Топ {limit} клиентов по выручке</CardTitle>
                <CardDescription>
                    Распределение выручки среди крупнейших клиентов за выбранный период.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {chartData.length === 0 ? (
                    <p className="text-muted-foreground text-sm">
                        Нет данных для отображения.
                    </p>
                ) : (
                    <ChartContainer
                        config={chartConfig}
                        className="aspect-auto h-[400px] md:h-[640px] w-full"
                    >
                        <BarChart
                            data={chartData}
                            layout="vertical"
                            margin={{ left: 16, right: 120, top: 24, bottom: 24 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                            <XAxis
                                type="number"
                                tickFormatter={formatCurrency}
                                tick={{ fontSize: 12 }}
                                domain={[0, 'dataMax']}
                            />
                            <YAxis
                                dataKey="name"
                                type="category"
                                width={120}
                                tickLine={false}
                                axisLine={false}
                                tick={{ fontSize: 12, width: 120, wordBreak: 'break-word' }}
                                interval={0}
                            />
                            <ChartTooltip
                                content={
                                    <ChartTooltipContent
                                        formatter={(value) => formatCurrency(Number(value))}
                                        labelFormatter={(label, payload) => {
                                            const [item] = payload ?? [];
                                            const percentage = item?.payload?.percentage;
                                            if (typeof percentage === 'number') {
                                                return `${label} — ${percentage.toFixed(1)}%`;
                                            }
                                            return label;
                                        }}
                                    />
                                }
                            />
                            <Bar
                                dataKey="total_revenue"
                                fill="var(--color-total_revenue)"
                                radius={[0, 4, 4, 0]}
                            >
                                <LabelList
                                    dataKey="total_revenue"
                                    position="right"
                                    offset={12}
                                    formatter={(value: number) => formatCurrency(value)}
                                    className="fill-foreground text-xs"
                                    style={{ fontWeight: 600 }}
                                />
                            </Bar>
                        </BarChart>
                    </ChartContainer>
                )}
            </CardContent>
        </Card>
    );
}


