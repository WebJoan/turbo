'use client';

import { useState, useCallback, useRef, type DragEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { createRFQ } from '@/lib/rfqs';
import { RFQCreateInput, RFQItemCreateInput } from '@/types/rfqs';
import { CompanySelector } from './rfq-company-selector';
import { PersonSelector } from './rfq-person-selector';
import { ProductSelector } from './rfq-product-selector';
import { IconPlus, IconTrash, IconLoader2, IconUpload, IconFile } from '@tabler/icons-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

// Schema for validation
const rfqCreateSchema = z.object({
    title: z.string().min(1, 'Название обязательно'),
    company_id: z.number().min(1, 'Выберите компанию'),
    contact_person_id: z.number().optional(),
    description: z.string().optional(),
    priority: z.enum(['low', 'medium', 'high', 'urgent']).default('medium'),
    deadline: z.string().optional(),
    delivery_address: z.string().optional(),
    payment_terms: z.string().optional(),
    delivery_terms: z.string().optional(),
    notes: z.string().optional(),
    items: z.array(z.object({
        product_type: z.enum(['new', 'existing']).default('new'),
        product_id: z.number().optional(),
        product_name: z.string().optional(),
        manufacturer: z.string().optional(),
        part_number: z.string().optional(),
        quantity: z.number().min(1, 'Количество должно быть больше 0'),
        unit: z.string().default('шт'),
        specifications: z.string().optional(),
        comments: z.string().optional(),
    }).refine((data) => {
        if (data.product_type === 'new') {
            return data.manufacturer && data.manufacturer.length > 0 &&
                data.part_number && data.part_number.length > 0;
        } else {
            return data.product_id && data.product_id > 0;
        }
    }, {
        message: 'Для нового товара укажите производителя и артикул, для товара из базы выберите товар',
        path: ['product_type']
    })).min(1, 'Добавьте хотя бы одну строку')
});

type RFQCreateFormData = z.infer<typeof rfqCreateSchema>;

const priorityLabels: Record<string, string> = {
    low: 'Низкий',
    medium: 'Средний',
    high: 'Высокий',
    urgent: 'Срочный'
};

const priorityVariants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    low: 'outline',
    medium: 'default',
    high: 'secondary',
    urgent: 'destructive'
};

export function RFQCreateForm() {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    // Храним выбранные файлы по ключу строки (stable id из useFieldArray)
    const [filesByRowKey, setFilesByRowKey] = useState<Record<string, File[]>>({});
    const [dragOverKey, setDragOverKey] = useState<string | null>(null);
    const fileInputsRef = useRef<Record<string, HTMLInputElement | null>>({});

    const form = useForm<RFQCreateFormData>({
        resolver: zodResolver(rfqCreateSchema),
        defaultValues: {
            title: '',
            description: '',
            priority: 'medium',
            deadline: '',
            delivery_address: '',
            payment_terms: '',
            delivery_terms: '',
            notes: '',
            items: [
                {
                    product_type: 'new',
                    product_id: undefined,
                    product_name: '',
                    manufacturer: '',
                    part_number: '',
                    quantity: 1,
                    unit: 'шт',
                    specifications: '',
                    comments: '',
                }
            ]
        }
    });

    const { fields, append, remove } = useFieldArray({
        control: form.control,
        name: 'items'
    });

    const addNewItem = useCallback(() => {
        append({
            product_type: 'new',
            product_id: undefined,
            product_name: '',
            manufacturer: '',
            part_number: '',
            quantity: 1,
            unit: 'шт',
            specifications: '',
            comments: '',
        });
    }, [append]);

    const removeItem = useCallback((index: number) => {
        if (fields.length > 1) {
            const key = fields[index].id;
            setFilesByRowKey(prev => {
                const next = { ...prev };
                delete next[key];
                return next;
            });
            remove(index);
        }
    }, [fields, remove]);

    const addFilesToRow = (rowKey: string, incoming: File[]) => {
        const maxBytes = 50 * 1024 * 1024;
        // Фильтруем слишком большие и дубли
        const valid = incoming.filter((f) => {
            if (f.size > maxBytes) {
                toast.error(`Файл "${f.name}" превышает 50 МБ`);
                return false;
            }
            return true;
        });
        if (valid.length === 0) return;

        setFilesByRowKey((prev) => {
            const existing = prev[rowKey] || [];
            const deduped = [...existing];
            for (const file of valid) {
                const duplicate = existing.some(
                    (e) => e.name === file.name && e.size === file.size && e.lastModified === file.lastModified
                );
                if (!duplicate) deduped.push(file);
            }
            return { ...prev, [rowKey]: deduped };
        });
    };

    const onFilesChange = (index: number, list: FileList | null) => {
        const key = fields[index].id;
        const files = Array.from(list || []);
        addFilesToRow(key, files);
    };

    const removeFileFromRow = (rowKey: string, fileIndex: number) => {
        setFilesByRowKey((prev) => {
            const current = prev[rowKey] || [];
            const next = current.filter((_, i) => i !== fileIndex);
            return { ...prev, [rowKey]: next };
        });
    };

    const handleDrop = (e: DragEvent<HTMLDivElement>, rowKey: string) => {
        e.preventDefault();
        e.stopPropagation();
        const dropped = Array.from(e.dataTransfer.files || []);
        addFilesToRow(rowKey, dropped);
        setDragOverKey(null);
    };

    const onSubmit = async (data: RFQCreateFormData) => {
        try {
            setIsSubmitting(true);

            const rfqData: RFQCreateInput = {
                title: data.title,
                company_id: data.company_id,
                contact_person_id: data.contact_person_id,
                description: data.description,
                priority: data.priority,
                deadline: data.deadline || null,
                delivery_address: data.delivery_address,
                payment_terms: data.payment_terms,
                delivery_terms: data.delivery_terms,
                notes: data.notes,
                items: data.items.map((item, index) => ({
                    line_number: index + 1,
                    product: item.product_type === 'existing' ? item.product_id : undefined,
                    product_name: item.product_name,
                    manufacturer: item.manufacturer,
                    part_number: item.part_number,
                    quantity: item.quantity,
                    unit: item.unit,
                    specifications: item.specifications,
                    comments: item.comments,
                    is_new_product: item.product_type === 'new',
                    files: filesByRowKey[fields[index].id]
                }))
            };

            const createdRFQ = await createRFQ(rfqData);
            toast.success(`RFQ ${createdRFQ.number} успешно создан!`);
            router.push(`/dashboard/rfqs`);

        } catch (error) {
            console.error('Error creating RFQ:', error);
            toast.error('Ошибка при создании RFQ. Попробуйте еще раз.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="space-y-6">
            <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                    {/* Основная информация RFQ */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                Основная информация
                                <span className="text-sm font-normal text-muted-foreground">
                                    (<span className="text-red-500">*</span> обязательные поля)
                                </span>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid gap-4 md:grid-cols-2">
                                <FormField
                                    control={form.control}
                                    name="title"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Название RFQ <span className="text-red-500">*</span></FormLabel>
                                            <FormControl>
                                                <Input placeholder="Введите название запроса" {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="priority"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Приоритет</FormLabel>
                                            <Select onValueChange={field.onChange} defaultValue={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    {Object.entries(priorityLabels).map(([value, label]) => (
                                                        <SelectItem key={value} value={value}>
                                                            <div className="flex items-center gap-2">
                                                                <Badge variant={priorityVariants[value]}>{label}</Badge>
                                                            </div>
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                            </div>

                            <FormField
                                control={form.control}
                                name="description"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Описание</FormLabel>
                                        <FormControl>
                                            <Textarea
                                                placeholder="Подробное описание запроса"
                                                className="min-h-[80px]"
                                                {...field}
                                            />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />

                            <div className="grid gap-4 md:grid-cols-2">
                                <FormField
                                    control={form.control}
                                    name="company_id"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Компания-заказчик <span className="text-red-500">*</span></FormLabel>
                                            <FormControl>
                                                <CompanySelector
                                                    value={field.value}
                                                    onValueChange={field.onChange}
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="contact_person_id"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Контактное лицо</FormLabel>
                                            <FormControl>
                                                <PersonSelector
                                                    value={field.value}
                                                    onValueChange={field.onChange}
                                                    companyId={form.watch('company_id')}
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                            </div>

                            <div className="grid gap-4 md:grid-cols-2">
                                <FormField
                                    control={form.control}
                                    name="deadline"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Крайний срок</FormLabel>
                                            <FormControl>
                                                <Input type="datetime-local" {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="delivery_address"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Адрес доставки</FormLabel>
                                            <FormControl>
                                                <Input placeholder="Адрес доставки товара" {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                            </div>

                            <div className="grid gap-4 md:grid-cols-2">
                                <FormField
                                    control={form.control}
                                    name="payment_terms"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Условия оплаты</FormLabel>
                                            <FormControl>
                                                <Input placeholder="Предоплата, постоплата и т.д." {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="delivery_terms"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Условия поставки</FormLabel>
                                            <FormControl>
                                                <Input placeholder="EXW, FCA, DAP и т.д." {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                            </div>

                            <FormField
                                control={form.control}
                                name="notes"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Заметки</FormLabel>
                                        <FormControl>
                                            <Textarea
                                                placeholder="Внутренние заметки и комментарии"
                                                className="min-h-[60px]"
                                                {...field}
                                            />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                        </CardContent>
                    </Card>

                    {/* Строки RFQ */}
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <CardTitle>Строки запроса</CardTitle>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={addNewItem}
                                    className="gap-2"
                                >
                                    <IconPlus className="h-4 w-4" />
                                    Добавить строку
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto border rounded-md">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="w-[50px]">№</TableHead>
                                            <TableHead className="min-w-[120px]">Тип товара</TableHead>
                                            <TableHead className="min-w-[200px]">Товар</TableHead>
                                            <TableHead className="min-w-[120px]">Производитель</TableHead>
                                            <TableHead className="w-[220px]">Файлы</TableHead>
                                            <TableHead className="min-w-[80px]">Кол-во *</TableHead>
                                            <TableHead className="min-w-[80px]">Ед.изм.</TableHead>
                                            <TableHead className="min-w-[150px]">Характеристики</TableHead>
                                            <TableHead className="min-w-[150px]">Комментарии</TableHead>
                                            <TableHead className="w-[50px]"></TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {fields.map((field, index) => {
                                            const productType = form.watch(`items.${index}.product_type`);
                                            const isNewProduct = productType === 'new';

                                            return (
                                                <TableRow key={field.id}>
                                                    <TableCell className="text-center font-medium">
                                                        {index + 1}
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.product_type`}
                                                            render={({ field }) => (
                                                                <div className="flex items-center space-x-2">
                                                                    <Switch
                                                                        checked={field.value === 'existing'}
                                                                        onCheckedChange={(checked) => {
                                                                            const newType = checked ? 'existing' : 'new';
                                                                            field.onChange(newType);
                                                                            // Очищаем поля при переключении
                                                                            if (newType === 'new') {
                                                                                form.setValue(`items.${index}.product_id`, undefined);
                                                                                form.setValue(`items.${index}.product_name`, '');
                                                                            } else {
                                                                                form.setValue(`items.${index}.manufacturer`, '');
                                                                                form.setValue(`items.${index}.part_number`, '');
                                                                            }
                                                                        }}
                                                                    />
                                                                    <Label className="text-xs">
                                                                        {field.value === 'existing' ? 'Из базы' : 'Новый'}
                                                                    </Label>
                                                                </div>
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        {isNewProduct ? (
                                                            <div className="space-y-2">
                                                                <FormField
                                                                    control={form.control}
                                                                    name={`items.${index}.product_name`}
                                                                    render={({ field }) => (
                                                                        <Input
                                                                            placeholder="Наименование товара"
                                                                            className="min-w-[180px]"
                                                                            {...field}
                                                                        />
                                                                    )}
                                                                />
                                                                <FormField
                                                                    control={form.control}
                                                                    name={`items.${index}.part_number`}
                                                                    render={({ field }) => (
                                                                        <FormItem>
                                                                            <FormControl>
                                                                                <Input
                                                                                    placeholder="Артикул *"
                                                                                    className="min-w-[180px]"
                                                                                    {...field}
                                                                                />
                                                                            </FormControl>
                                                                            <FormMessage />
                                                                        </FormItem>
                                                                    )}
                                                                />
                                                            </div>
                                                        ) : (
                                                            <FormField
                                                                control={form.control}
                                                                name={`items.${index}.product_id`}
                                                                render={({ field }) => (
                                                                    <FormItem>
                                                                        <FormControl>
                                                                            <ProductSelector
                                                                                value={field.value}
                                                                                onValueChange={field.onChange}
                                                                                onProductSelect={(product) => {
                                                                                    if (product) {
                                                                                        // Для отображения в таблице используем краткое имя (part number)
                                                                                        form.setValue(`items.${index}.product_name`, product.name);
                                                                                        form.setValue(`items.${index}.manufacturer`, product.brand_name || '');
                                                                                    }
                                                                                }}
                                                                                placeholder="Выберите товар из базы"
                                                                            />
                                                                        </FormControl>
                                                                        <FormMessage />
                                                                    </FormItem>
                                                                )}
                                                            />
                                                        )}
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.manufacturer`}
                                                            render={({ field }) => (
                                                                <FormItem>
                                                                    <FormControl>
                                                                        <Input
                                                                            placeholder={isNewProduct ? "Производитель *" : "Автозаполнение"}
                                                                            className="min-w-[120px]"
                                                                            disabled={!isNewProduct}
                                                                            {...field}
                                                                        />
                                                                    </FormControl>
                                                                    {isNewProduct && <FormMessage />}
                                                                </FormItem>
                                                            )}
                                                        />
                                                    </TableCell>
                                                    {/* Файлы c drag-and-drop */}
                                                    <TableCell>
                                                        <div className="space-y-2 w-[220px] max-w-[220px]">
                                                            <input
                                                                ref={(el) => { fileInputsRef.current[field.id] = el; }}
                                                                type="file"
                                                                multiple
                                                                className="hidden"
                                                                onChange={(e) => onFilesChange(index, e.target.files)}
                                                            />
                                                            <div
                                                                role="button"
                                                                tabIndex={0}
                                                                onClick={() => fileInputsRef.current[field.id]?.click()}
                                                                onKeyDown={(e) => {
                                                                    if (e.key === 'Enter' || e.key === ' ') fileInputsRef.current[field.id]?.click();
                                                                }}
                                                                onDragOver={(e) => { e.preventDefault(); setDragOverKey(field.id); }}
                                                                onDragEnter={() => setDragOverKey(field.id)}
                                                                onDragLeave={() => setDragOverKey((k) => (k === field.id ? null : k))}
                                                                onDrop={(e) => handleDrop(e as unknown as DragEvent<HTMLDivElement>, field.id)}
                                                                className={
                                                                    `flex items-center gap-2 justify-center rounded-md border border-dashed p-3 text-xs cursor-pointer transition-colors ` +
                                                                    (dragOverKey === field.id ? 'bg-primary/10 border-primary' : 'hover:bg-muted/50')
                                                                }
                                                            >
                                                                <IconUpload className="h-4 w-4" />
                                                                <span className="truncate">
                                                                    Перетащите файлы или нажмите, чтобы выбрать
                                                                </span>
                                                            </div>
                                                            {(filesByRowKey[field.id]?.length || 0) > 0 && (
                                                                <ul className="space-y-1 w-full">
                                                                    {filesByRowKey[field.id]!.map((f, fi) => (
                                                                        <li key={`${f.name}-${f.lastModified}`} className="flex items-center gap-2 text-[11px] w-full overflow-hidden">
                                                                            <IconFile className="h-3.5 w-3.5 text-muted-foreground" />
                                                                            <span className="truncate flex-1" title={f.name}>{f.name}</span>
                                                                            <span className="text-muted-foreground">{(f.size / (1024 * 1024)).toFixed(1)} МБ</span>
                                                                            <Button
                                                                                type="button"
                                                                                variant="ghost"
                                                                                size="icon"
                                                                                className="h-6 w-6 p-0"
                                                                                onClick={() => removeFileFromRow(field.id, fi)}
                                                                                aria-label="Удалить файл"
                                                                            >
                                                                                <IconTrash className="h-3.5 w-3.5" />
                                                                            </Button>
                                                                        </li>
                                                                    ))}
                                                                </ul>
                                                            )}
                                                            <div className="text-[10px] text-muted-foreground">
                                                                до 50 МБ каждый, можно добавить несколько
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.quantity`}
                                                            render={({ field }) => (
                                                                <FormItem>
                                                                    <FormControl>
                                                                        <Input
                                                                            type="number"
                                                                            min="1"
                                                                            className="min-w-[80px]"
                                                                            {...field}
                                                                            onChange={(e) => field.onChange(parseInt(e.target.value) || 1)}
                                                                        />
                                                                    </FormControl>
                                                                    <FormMessage />
                                                                </FormItem>
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.unit`}
                                                            render={({ field }) => (
                                                                <Select onValueChange={field.onChange} defaultValue={field.value}>
                                                                    <SelectTrigger className="min-w-[80px]">
                                                                        <SelectValue />
                                                                    </SelectTrigger>
                                                                    <SelectContent>
                                                                        <SelectItem value="шт">шт</SelectItem>
                                                                        <SelectItem value="кг">кг</SelectItem>
                                                                        <SelectItem value="м">м</SelectItem>
                                                                        <SelectItem value="м²">м²</SelectItem>
                                                                        <SelectItem value="м³">м³</SelectItem>
                                                                        <SelectItem value="л">л</SelectItem>
                                                                        <SelectItem value="комп.">комп.</SelectItem>
                                                                        <SelectItem value="упак.">упак.</SelectItem>
                                                                    </SelectContent>
                                                                </Select>
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.specifications`}
                                                            render={({ field }) => (
                                                                <Textarea
                                                                    placeholder="Технические характеристики"
                                                                    className="min-w-[150px] min-h-[60px]"
                                                                    {...field}
                                                                />
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.comments`}
                                                            render={({ field }) => (
                                                                <Textarea
                                                                    placeholder="Комментарии"
                                                                    className="min-w-[150px] min-h-[60px]"
                                                                    {...field}
                                                                />
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <Button
                                                            type="button"
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => removeItem(index)}
                                                            disabled={fields.length === 1}
                                                            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                                                        >
                                                            <IconTrash className="h-4 w-4" />
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </div>
                            {fields.length > 0 && (
                                <div className="mt-4 p-3 bg-muted/30 rounded-lg">
                                    <div className="text-sm text-muted-foreground mb-2">
                                        <span className="text-red-500">*</span> Обязательные поля
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                        Всего строк: {fields.length}
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Кнопки действий */}
                    <div className="flex flex-col sm:flex-row justify-end gap-3 pt-6 border-t">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => router.back()}
                            disabled={isSubmitting}
                            className="w-full sm:w-auto"
                        >
                            Отмена
                        </Button>
                        <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
                            {isSubmitting ? (
                                <>
                                    <IconLoader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Создание...
                                </>
                            ) : (
                                'Создать RFQ'
                            )}
                        </Button>
                    </div>
                </form>
            </Form>
        </div>
    );
}
