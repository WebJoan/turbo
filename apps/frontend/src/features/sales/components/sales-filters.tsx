'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { SalesFilters } from '@/types/sales';
import { FilterIcon, XIcon } from 'lucide-react';

interface SalesFiltersProps {
  onFiltersChange: (filters: SalesFilters) => void;
  initialFilters?: SalesFilters;
}

export function SalesFiltersComponent({
  onFiltersChange,
  initialFilters = {}
}: SalesFiltersProps) {
  const [filters, setFilters] = useState<SalesFilters>(initialFilters);
  const [isOpen, setIsOpen] = useState(false);

  const handleChange = (key: keyof SalesFilters, value: any) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
  };

  const handleApply = () => {
    onFiltersChange(filters);
    setIsOpen(false);
  };

  const handleReset = () => {
    const emptyFilters: SalesFilters = {};
    setFilters(emptyFilters);
    onFiltersChange(emptyFilters);
  };

  const activeFiltersCount = Object.values(filters).filter(
    (v) => v !== undefined && v !== null && v !== ''
  ).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={() => setIsOpen(!isOpen)}
          className="gap-2"
        >
          <FilterIcon className="h-4 w-4" />
          Фильтры
          {activeFiltersCount > 0 && (
            <span className="ml-1 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
              {activeFiltersCount}
            </span>
          )}
        </Button>
        {activeFiltersCount > 0 && (
          <Button variant="ghost" size="sm" onClick={handleReset}>
            <XIcon className="mr-1 h-4 w-4" />
            Сбросить
          </Button>
        )}
      </div>

      {isOpen && (
        <Card>
          <CardHeader>
            <CardTitle>Фильтры аналитики продаж</CardTitle>
            <CardDescription>
              Настройте параметры для отображения данных
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Период времени */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="date_from">Дата от</Label>
                <Input
                  id="date_from"
                  type="date"
                  value={filters.date_from || ''}
                  onChange={(e) => handleChange('date_from', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="date_to">Дата до</Label>
                <Input
                  id="date_to"
                  type="date"
                  value={filters.date_to || ''}
                  onChange={(e) => handleChange('date_to', e.target.value)}
                />
              </div>
            </div>

            {/* Тип периода */}
            <div className="space-y-2">
              <Label htmlFor="period_type">Группировка по периоду</Label>
              <Select
                value={filters.period_type || 'month'}
                onValueChange={(value) =>
                  handleChange('period_type', value as SalesFilters['period_type'])
                }
              >
                <SelectTrigger id="period_type">
                  <SelectValue placeholder="Выберите период" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="day">День</SelectItem>
                  <SelectItem value="week">Неделя</SelectItem>
                  <SelectItem value="month">Месяц</SelectItem>
                  <SelectItem value="year">Год</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Тип продажи */}
            <div className="space-y-2">
              <Label htmlFor="sale_type">Тип продажи</Label>
              <Select
                value={filters.sale_type || undefined}
                onValueChange={(value) =>
                  handleChange('sale_type', value === 'all' ? undefined : value)
                }
              >
                <SelectTrigger id="sale_type">
                  <SelectValue placeholder="Все типы" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Все типы</SelectItem>
                  <SelectItem value="stock">Со склада</SelectItem>
                  <SelectItem value="order">Под заказ</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Валюта */}
            <div className="space-y-2">
              <Label htmlFor="currency">Валюта</Label>
              <Select
                value={filters.currency || undefined}
                onValueChange={(value) =>
                  handleChange('currency', value === 'all' ? undefined : value)
                }
              >
                <SelectTrigger id="currency">
                  <SelectValue placeholder="Все валюты" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Все валюты</SelectItem>
                  <SelectItem value="RUB">Рубли (RUB)</SelectItem>
                  <SelectItem value="USD">Доллары (USD)</SelectItem>
                  <SelectItem value="CNY">Юани (CNY)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Кнопки действий */}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsOpen(false)}>
                Отмена
              </Button>
              <Button onClick={handleApply}>Применить</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

