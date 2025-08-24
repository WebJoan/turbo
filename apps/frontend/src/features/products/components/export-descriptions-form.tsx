'use client';

import { useState, useMemo, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage
} from '@/components/ui/form';
import { Checkbox } from '@/components/ui/checkbox';
import { Loader2, Download, AlertCircle, X } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from 'sonner';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { Check, ChevronsUpDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
    fetchSubgroupsAutocomplete,
    fetchBrandsAutocomplete,
    exportProductDescriptions,
    ProductSubgroup,
    Brand
} from '@/lib/product-subgroups';

const exportFormSchema = z.object({
    selectedSubgroups: z.array(z.string()).optional(),
    selectedBrands: z.array(z.string()).optional(),
    onlyTwoParams: z.boolean().optional(),
    noDescription: z.boolean().optional()
});

type ExportFormValues = z.infer<typeof exportFormSchema>;

export function ExportDescriptionsForm() {
    const [loading, setLoading] = useState(false);

    // Состояние для подгрупп
    const [subgroups, setSubgroups] = useState<ProductSubgroup[]>([]);
    const [subgroupSearchQuery, setSubgroupSearchQuery] = useState('');
    const [subgroupOpen, setSubgroupOpen] = useState(false);
    const [selectedSubgroups, setSelectedSubgroups] = useState<ProductSubgroup[]>([]);

    // Состояние для брендов
    const [brands, setBrands] = useState<Brand[]>([]);
    const [brandSearchQuery, setBrandSearchQuery] = useState('');
    const [brandOpen, setBrandOpen] = useState(false);
    const [selectedBrands, setSelectedBrands] = useState<Brand[]>([]);

    const form = useForm<ExportFormValues>({
        resolver: zodResolver(exportFormSchema),
        defaultValues: {
            selectedSubgroups: [],
            selectedBrands: [],
            onlyTwoParams: false,
            noDescription: false
        }
    });

    // Функция для загрузки подгрупп с автокомплитом
    const fetchSubgroups = async (query: string = '') => {
        try {
            const data = await fetchSubgroupsAutocomplete(query, 20);
            setSubgroups(data);
        } catch (error) {
            console.error('Error fetching subgroups:', error);
            toast.error('Не удалось загрузить список подгрупп');
        }
    };

    // Функция для загрузки брендов с автокомплитом
    const fetchBrands = async (query: string = '') => {
        try {
            const data = await fetchBrandsAutocomplete(query, 20);
            setBrands(data);
        } catch (error) {
            console.error('Error fetching brands:', error);
            toast.error('Не удалось загрузить список брендов');
        }
    };

    // Загружаем подгруппы при изменении поискового запроса
    useEffect(() => {
        const timeoutId = setTimeout(() => {
            fetchSubgroups(subgroupSearchQuery);
        }, 300);

        return () => clearTimeout(timeoutId);
    }, [subgroupSearchQuery]);

    // Загружаем бренды при изменении поискового запроса
    useEffect(() => {
        const timeoutId = setTimeout(() => {
            fetchBrands(brandSearchQuery);
        }, 300);

        return () => clearTimeout(timeoutId);
    }, [brandSearchQuery]);

    // Загружаем начальные списки
    useEffect(() => {
        fetchSubgroups();
        fetchBrands();
    }, []);

    // Обработчики для подгрупп
    const handleSubgroupSelect = (subgroup: ProductSubgroup) => {
        const isAlreadySelected = selectedSubgroups.some(s => s.id === subgroup.id);
        if (!isAlreadySelected) {
            const newSelection = [...selectedSubgroups, subgroup];
            setSelectedSubgroups(newSelection);
            form.setValue('selectedSubgroups', newSelection.map(s => s.ext_id));
            form.trigger('selectedSubgroups'); // Принудительно обновляем валидацию
        }
        setSubgroupOpen(false);
    };

    const handleSubgroupRemove = (subgroupId: number) => {
        console.log('Removing subgroup with id:', subgroupId);
        const newSelection = selectedSubgroups.filter(s => s.id !== subgroupId);
        console.log('New subgroups selection:', newSelection);
        setSelectedSubgroups(newSelection);
        form.setValue('selectedSubgroups', newSelection.map(s => s.ext_id));
        form.trigger('selectedSubgroups'); // Принудительно обновляем валидацию
    };

    // Обработчики для брендов
    const handleBrandSelect = (brand: Brand) => {
        const isAlreadySelected = selectedBrands.some(b => b.id === brand.id);
        if (!isAlreadySelected) {
            const newSelection = [...selectedBrands, brand];
            setSelectedBrands(newSelection);
            form.setValue('selectedBrands', newSelection.map(b => b.name));
            form.trigger('selectedBrands'); // Принудительно обновляем валидацию
        }
        setBrandOpen(false);
    };

    const handleBrandRemove = (brandId: number) => {
        console.log('Removing brand with id:', brandId);
        const newSelection = selectedBrands.filter(b => b.id !== brandId);
        console.log('New brands selection:', newSelection);
        setSelectedBrands(newSelection);
        form.setValue('selectedBrands', newSelection.map(b => b.name));
        form.trigger('selectedBrands'); // Принудительно обновляем валидацию
    };

    const onSubmit = async (data: ExportFormValues) => {
        setLoading(true);
        try {
            const response = await exportProductDescriptions(
                undefined, // typecode не используем
                false, // синхронный экспорт
                data.selectedSubgroups,
                data.selectedBrands,
                data.onlyTwoParams,
                data.noDescription
            );

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(errorData?.error || 'Ошибка при экспорте');
            }

            // Если ответ успешный, получаем файл
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;

            // Получаем имя файла из заголовков ответа
            const contentDisposition = response.headers.get('content-disposition');
            let filename = 'export.xlsx';
            if (contentDisposition) {
                const matches = /filename="(.+)"/.exec(contentDisposition);
                if (matches != null) {
                    filename = matches[1];
                }
            }

            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

            toast.success(`Файл ${filename} загружен`);
        } catch (error) {
            console.error('Export error:', error);
            toast.error(error instanceof Error ? error.message : 'Произошла неизвестная ошибка');
        } finally {
            setLoading(false);
        }
    };

    const filteredSubgroups = useMemo(() => {
        if (!subgroupSearchQuery) return subgroups;
        return subgroups.filter(subgroup =>
            subgroup.display_name.toLowerCase().includes(subgroupSearchQuery.toLowerCase())
        );
    }, [subgroups, subgroupSearchQuery]);

    const filteredBrands = useMemo(() => {
        if (!brandSearchQuery) return brands;
        return brands.filter(brand =>
            brand.name.toLowerCase().includes(brandSearchQuery.toLowerCase())
        );
    }, [brands, brandSearchQuery]);

    return (
        <div className='max-w-4xl space-y-6'>
            <Alert>
                <AlertCircle className='h-4 w-4' />
                <AlertDescription>
                    Выберите подгруппы товаров и/или бренды для экспорта описательных свойств в Excel файл.
                    Экспорт включает артикул, группу, подгруппу, тип продукции, бренд, названия и описания товаров.
                    Можно выбрать только подгруппы, только бренды, и то и другое для точной фильтрации,
                    или оставить поля пустыми для экспорта всех товаров.
                </AlertDescription>
            </Alert>

            <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-6'>
                    {/* Выбор подгрупп */}
                    <FormField
                        control={form.control}
                        name='selectedSubgroups'
                        render={() => (
                            <FormItem className='flex flex-col'>
                                <FormLabel>Подгруппы товаров (опционально)</FormLabel>
                                <div className='space-y-3'>
                                    <Popover open={subgroupOpen} onOpenChange={setSubgroupOpen}>
                                        <PopoverTrigger asChild>
                                            <FormControl>
                                                <Button
                                                    variant='outline'
                                                    role='combobox'
                                                    className={cn(
                                                        'w-full justify-between',
                                                        selectedSubgroups.length === 0 && 'text-muted-foreground'
                                                    )}
                                                >
                                                    {selectedSubgroups.length > 0
                                                        ? `Выбрано подгрупп: ${selectedSubgroups.length}`
                                                        : 'Выберите подгруппы...'
                                                    }
                                                    <ChevronsUpDown className='ml-2 h-4 w-4 shrink-0 opacity-50' />
                                                </Button>
                                            </FormControl>
                                        </PopoverTrigger>
                                        <PopoverContent className='w-full p-0'>
                                            <Command>
                                                <CommandInput
                                                    placeholder='Поиск подгруппы...'
                                                    value={subgroupSearchQuery}
                                                    onValueChange={setSubgroupSearchQuery}
                                                />
                                                <CommandEmpty>Подгруппы не найдены.</CommandEmpty>
                                                <CommandList>
                                                    {filteredSubgroups.map((subgroup) => (
                                                        <CommandItem
                                                            value={subgroup.display_name}
                                                            key={subgroup.id}
                                                            onSelect={() => handleSubgroupSelect(subgroup)}
                                                        >
                                                            <Check
                                                                className={cn(
                                                                    'mr-2 h-4 w-4',
                                                                    selectedSubgroups.some(s => s.id === subgroup.id)
                                                                        ? 'opacity-100'
                                                                        : 'opacity-0'
                                                                )}
                                                            />
                                                            {subgroup.display_name}
                                                        </CommandItem>
                                                    ))}
                                                </CommandList>
                                            </Command>
                                        </PopoverContent>
                                    </Popover>

                                    {/* Список выбранных подгрупп */}
                                    {selectedSubgroups.length > 0 && (
                                        <div className='flex flex-wrap gap-2'>
                                            {selectedSubgroups.map((subgroup) => (
                                                <Badge key={subgroup.id} variant='secondary' className='flex items-center gap-1 pr-1'>
                                                    <span className='mr-1'>{subgroup.display_name}</span>
                                                    <button
                                                        type='button'
                                                        className='flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-500 transition-colors'
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            handleSubgroupRemove(subgroup.id);
                                                        }}
                                                        aria-label={`Удалить ${subgroup.display_name}`}
                                                    >
                                                        <X className='h-3 w-3' />
                                                    </button>
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    {/* Выбор брендов */}
                    <FormField
                        control={form.control}
                        name='selectedBrands'
                        render={() => (
                            <FormItem className='flex flex-col'>
                                <FormLabel>Бренды (опционально)</FormLabel>
                                <div className='space-y-3'>
                                    <Popover open={brandOpen} onOpenChange={setBrandOpen}>
                                        <PopoverTrigger asChild>
                                            <FormControl>
                                                <Button
                                                    variant='outline'
                                                    role='combobox'
                                                    className={cn(
                                                        'w-full justify-between',
                                                        selectedBrands.length === 0 && 'text-muted-foreground'
                                                    )}
                                                >
                                                    {selectedBrands.length > 0
                                                        ? `Выбрано брендов: ${selectedBrands.length}`
                                                        : 'Выберите бренды...'
                                                    }
                                                    <ChevronsUpDown className='ml-2 h-4 w-4 shrink-0 opacity-50' />
                                                </Button>
                                            </FormControl>
                                        </PopoverTrigger>
                                        <PopoverContent className='w-full p-0'>
                                            <Command>
                                                <CommandInput
                                                    placeholder='Поиск бренда...'
                                                    value={brandSearchQuery}
                                                    onValueChange={setBrandSearchQuery}
                                                />
                                                <CommandEmpty>Бренды не найдены.</CommandEmpty>
                                                <CommandList>
                                                    {filteredBrands.map((brand) => (
                                                        <CommandItem
                                                            value={brand.name}
                                                            key={brand.id}
                                                            onSelect={() => handleBrandSelect(brand)}
                                                        >
                                                            <Check
                                                                className={cn(
                                                                    'mr-2 h-4 w-4',
                                                                    selectedBrands.some(b => b.id === brand.id)
                                                                        ? 'opacity-100'
                                                                        : 'opacity-0'
                                                                )}
                                                            />
                                                            {brand.name}
                                                            {brand.product_manager && (
                                                                <span className='ml-auto text-xs text-muted-foreground'>
                                                                    {brand.product_manager}
                                                                </span>
                                                            )}
                                                        </CommandItem>
                                                    ))}
                                                </CommandList>
                                            </Command>
                                        </PopoverContent>
                                    </Popover>

                                    {/* Список выбранных брендов */}
                                    {selectedBrands.length > 0 && (
                                        <div className='flex flex-wrap gap-2 max-h-32 overflow-y-auto'>
                                            {selectedBrands.map((brand) => (
                                                <Badge key={brand.id} variant='secondary' className='flex items-center gap-1 pr-1'>
                                                    <span className='mr-1'>{brand.name}</span>
                                                    <button
                                                        type='button'
                                                        className='flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-500 transition-colors'
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            handleBrandRemove(brand.id);
                                                        }}
                                                        aria-label={`Удалить ${brand.name}`}
                                                    >
                                                        <X className='h-3 w-3' />
                                                    </button>
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    {/* Чекбокс для фильтрации по двум техническим параметрам */}
                    <FormField
                        control={form.control}
                        name='onlyTwoParams'
                        render={({ field }) => (
                            <FormItem className='flex flex-row items-start space-x-3 space-y-0'>
                                <FormControl>
                                    <Checkbox
                                        checked={field.value}
                                        onCheckedChange={field.onChange}
                                    />
                                </FormControl>
                                <div className='space-y-1 leading-none'>
                                    <FormLabel>
                                        Только товары с двумя техническими параметрами
                                    </FormLabel>
                                    <p className='text-sm text-muted-foreground'>
                                        При активации экспортируются только товары, имеющие ровно 2 технических параметра
                                    </p>
                                </div>
                            </FormItem>
                        )}
                    />

                    {/* Чекбокс для фильтрации товаров без описания */}
                    <FormField
                        control={form.control}
                        name='noDescription'
                        render={({ field }) => (
                            <FormItem className='flex flex-row items-start space-x-3 space-y-0'>
                                <FormControl>
                                    <Checkbox
                                        checked={field.value}
                                        onCheckedChange={field.onChange}
                                    />
                                </FormControl>
                                <div className='space-y-1 leading-none'>
                                    <FormLabel>
                                        Только товары без описания
                                    </FormLabel>
                                    <p className='text-sm text-muted-foreground'>
                                        При активации экспортируются только товары с пустым или отсутствующим описанием
                                    </p>
                                </div>
                            </FormItem>
                        )}
                    />

                    <Button type='submit' disabled={loading} className='w-full'>
                        {loading ? (
                            <>
                                <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                                Экспортируем...
                            </>
                        ) : (
                            <>
                                <Download className='mr-2 h-4 w-4' />
                                Экспортировать в Excel
                            </>
                        )}
                    </Button>
                </form>
            </Form>
        </div>
    );
}