'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { PriceComparison } from '@/types/stock';
import { fetchPriceComparisonClient, formatPrice, formatStockStatus, formatMatchType } from '@/lib/stock-client';
import { TrendingUp, TrendingDown, Minus, Package, Clock, AlertCircle } from 'lucide-react';

interface PriceComparisonViewProps {
    productId: number;
}

export function PriceComparisonView({ productId }: PriceComparisonViewProps) {
    const [comparison, setComparison] = useState<PriceComparison | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadComparison = async () => {
            try {
                setLoading(true);
                const data = await fetchPriceComparisonClient(productId);
                setComparison(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Ошибка загрузки данных');
            } finally {
                setLoading(false);
            }
        };

        loadComparison();
    }, [productId]);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            </div>
        );
    }

    if (error || !comparison) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <AlertCircle className="h-5 w-5 text-red-500" />
                        Ошибка загрузки данных
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-red-600">{error || 'Данные не найдены'}</p>
                </CardContent>
            </Card>
        );
    }

    const getPriceTrend = (competitorPrice: number | null, ourPrice: number | null) => {
        if (!competitorPrice || !ourPrice) return null;

        const diff = ((competitorPrice - ourPrice) / ourPrice) * 100;

        if (Math.abs(diff) < 1) {
            return {
                icon: Minus,
                color: 'text-gray-500',
                text: '≈',
                value: diff,
            };
        }

        if (diff > 0) {
            return {
                icon: TrendingUp,
                color: 'text-red-500',
                text: '↑',
                value: diff,
            };
        }

        return {
            icon: TrendingDown,
            color: 'text-green-500',
            text: '↓',
            value: Math.abs(diff),
        };
    };

    return (
        <div className="space-y-6">
            {/* Основная информация о товаре */}
            <Card>
                <CardHeader>
                    <CardTitle>{comparison.our_product_name}</CardTitle>
                    <CardDescription>
                        Текущая цена: {formatPrice(comparison.our_current_price)}
                    </CardDescription>
                </CardHeader>
            </Card>

            {/* История наших цен */}
            <Card>
                <CardHeader>
                    <CardTitle>История наших цен</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-2">
                        {comparison.our_price_history.slice(0, 5).map((history) => (
                            <div key={history.id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-b-0">
                                <span className="text-sm text-gray-600">
                                    {new Date(history.moment).toLocaleDateString('ru-RU')}
                                </span>
                                <div className="flex items-center gap-2">
                                    <span className="font-medium">{formatPrice(history.price_ex_vat)}</span>
                                    {history.vat_rate && (
                                        <Badge variant="outline" className="text-xs">
                                            НДС: {(history.vat_rate * 100).toFixed(0)}%
                                        </Badge>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Таблица цен: наши против конкурентов */}
            <Card>
                <CardHeader>
                    <CardTitle>Сравнительная таблица цен</CardTitle>
                    <CardDescription>Наша текущая цена и цены конкурентов</CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Конкурент</TableHead>
                                <TableHead>Артикул</TableHead>
                                <TableHead className="text-right">Цена конкурента</TableHead>
                                <TableHead className="text-right">Наша цена</TableHead>
                                <TableHead className="text-right">Разница</TableHead>
                                <TableHead>Наличие</TableHead>
                                <TableHead>Обновлено</TableHead>
                                <TableHead>Доставка</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {comparison.competitor_prices.map((price) => {
                                const trend = getPriceTrend(price.price_ex_vat, comparison.our_current_price);
                                const TrendIcon = trend?.icon || Minus;
                                return (
                                    <TableRow key={price.id}>
                                        <TableCell className="font-medium whitespace-nowrap">{price.competitor_name}</TableCell>
                                        <TableCell className="text-muted-foreground whitespace-nowrap">{price.product_part_number}</TableCell>
                                        <TableCell className="text-right whitespace-nowrap">
                                            {formatPrice(price.price_ex_vat, price.currency)}
                                            {price.vat_rate && (
                                                <Badge variant="outline" className="ml-2 text-[10px]">НДС {(price.vat_rate * 100).toFixed(0)}%</Badge>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right whitespace-nowrap">{formatPrice(comparison.our_current_price)}</TableCell>
                                        <TableCell className="text-right whitespace-nowrap">
                                            {trend && (
                                                <span className={`inline-flex items-center gap-1 ${trend.color}`}>
                                                    <TrendIcon className="h-4 w-4" />
                                                    {trend.value.toFixed(1)}%
                                                </span>
                                            )}
                                        </TableCell>
                                        <TableCell className="whitespace-nowrap">
                                            <span>{formatStockStatus(price.stock_status)}</span>
                                            {price.stock_qty && <span className="text-xs text-muted-foreground ml-1">({price.stock_qty} шт.)</span>}
                                        </TableCell>
                                        <TableCell className="whitespace-nowrap">{new Date(price.collected_at).toLocaleDateString('ru-RU')}</TableCell>
                                        <TableCell className="whitespace-nowrap">
                                            {price.delivery_days_min && (
                                                <span>
                                                    {price.delivery_days_min}
                                                    {price.delivery_days_max && price.delivery_days_max !== price.delivery_days_min ? `-${price.delivery_days_max}` : ''} дн.
                                                </span>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                            {comparison.competitor_prices.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                                        <Package className="h-5 w-5 inline-block mr-2 opacity-60" />Цены конкурентов не найдены
                                        </TableCell>
                                    </TableRow>
                                )}
                        </TableBody>
                        {comparison.our_current_price !== null && (
                            <TableCaption>Наша текущая цена: {formatPrice(comparison.our_current_price)}</TableCaption>
                        )}
                    </Table>
                </CardContent>
            </Card>

            {/* Сопоставления товаров */}
            {comparison.matches.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Сопоставления товаров</CardTitle>
                        <CardDescription>
                            Автоматические и ручные сопоставления с товарами конкурентов
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {comparison.matches.map((match) => (
                                <div key={match.id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-b-0">
                                    <div>
                                        <span className="font-medium">{match.competitor_product.part_number}</span>
                                        <span className="text-sm text-gray-600 ml-2">
                                            ({match.competitor_product.competitor.name})
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant={
                                            match.match_type === 'exact' ? 'default' :
                                                match.match_type === 'equivalent' ? 'secondary' :
                                                    'outline'
                                        }>
                                            {formatMatchType(match.match_type)}
                                        </Badge>
                                        <span className="text-sm text-gray-600">
                                            {match.confidence.toFixed(0)}%
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
