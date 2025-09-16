'use client';

import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
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
import { fetchRFQById, updateRFQ, updateRFQItem, createRFQItem, deleteRFQItem, uploadFilesForRFQItem, deleteRFQItemFile } from '@/lib/rfqs';
import { RFQ, RFQItem } from '@/types/rfqs';
import { CompanySelector } from './rfq-company-selector';
import { PersonSelector } from './rfq-person-selector';
import { ProductSelector } from './rfq-product-selector';
import { IconPlus, IconTrash, IconLoader2, IconUpload, IconFile } from '@tabler/icons-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import FormCardSkeleton from '@/components/form-card-skeleton';
import { DataTableSkeleton } from '@/components/ui/table/data-table-skeleton';

const rfqEditSchema = z.object({
    description: z.string().optional(),
    priority: z.enum(['low', 'medium', 'high', 'urgent']).default('medium'),
    deadline: z.string().nullable().optional(),
    delivery_address: z.string().optional(),
    payment_terms: z.string().optional(),
    delivery_terms: z.string().optional(),
    notes: z.string().optional(),
    company_id: z.number().min(1, 'Выберите компанию'),
    contact_person_id: z.number().nullable().optional(),
    items: z.array(z.object({
        id: z.number().optional(),
        line_number: z.number().min(1),
        product_type: z.enum(['new', 'existing']).default('new'),
        product_id: z.number().optional(),
        product_name: z.string().optional(),
        manufacturer: z.string().optional(),
        part_number: z.string().optional(),
        quantity: z.number().min(1, 'Количество должно быть больше 0'),
        unit: z.string().default('шт'),
        specifications: z.string().optional(),
        comments: z.string().optional(),
        files: z.any().optional(),
        _status: z.enum(['unchanged', 'new', 'updated', 'deleted']).optional(),
    })).min(1, 'Добавьте хотя бы одну строку')
});

type RFQEditFormData = z.infer<typeof rfqEditSchema>;

const priorityLabels: Record<string, string> = { low: 'Низкий', medium: 'Средний', high: 'Высокий', urgent: 'Срочный' };
const priorityVariants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    low: 'outline',
    medium: 'default',
    high: 'secondary',
    urgent: 'destructive'
};

type Props = { rfqId: number };

export function RFQEditForm({ rfqId }: Props) {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loading, setLoading] = useState(true);
    const [rfq, setRfq] = useState<RFQ | null>(null);
    const fileInputsRef = useRef<Record<string, HTMLInputElement | null>>({});
    const [filesByRowKey, setFilesByRowKey] = useState<Record<string, File[]>>({});
    const [dragOverKey, setDragOverKey] = useState<string | null>(null);

    const form = useForm<RFQEditFormData>({
        resolver: zodResolver(rfqEditSchema),
        defaultValues: {
            description: '',
            priority: 'medium',
            deadline: null,
            delivery_address: '',
            payment_terms: '',
            delivery_terms: '',
            notes: '',
            company_id: undefined as unknown as number,
            contact_person_id: null,
            items: []
        }
    });

    const { fields, append, remove, replace } = useFieldArray({ control: form.control, name: 'items' });

    // Преобразование ISO -> формат для input type="datetime-local"
    const toDateTimeLocal = (iso: string | null | undefined): string => {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            const yyyy = String(d.getFullYear());
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            const hh = String(d.getHours()).padStart(2, '0');
            const min = String(d.getMinutes()).padStart(2, '0');
            return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
        } catch {
            return '';
        }
    };

    useEffect(() => {
        const load = async () => {
            try {
                setLoading(true);
                const data = await fetchRFQById(rfqId);
                setRfq(data);

                replace(
                    data.items
                        .sort((a, b) => a.line_number - b.line_number)
                        .map((it) => ({
                            id: it.id,
                            line_number: it.line_number,
                            product_type: it.product ? 'existing' : 'new',
                            product_id: it.product || undefined,
                            product_name: it.product_name || '',
                            manufacturer: it.manufacturer || '',
                            part_number: it.part_number || '',
                            quantity: it.quantity,
                            unit: it.unit || 'шт',
                            specifications: it.specifications || '',
                            comments: it.comments || '',
                            _status: 'unchanged',
                        }))
                );

                form.reset({
                    description: data.description || '',
                    priority: data.priority,
                    deadline: toDateTimeLocal(data.deadline),
                    delivery_address: data.delivery_address || '',
                    payment_terms: data.payment_terms || '',
                    delivery_terms: data.delivery_terms || '',
                    notes: data.notes || '',
                    company_id: Number(data.company),
                    contact_person_id: data.contact_person || null,
                    items: data.items.map((it) => ({
                        id: it.id,
                        line_number: it.line_number,
                        product_type: it.product ? 'existing' : 'new',
                        product_id: it.product || undefined,
                        product_name: it.product_name || '',
                        manufacturer: it.manufacturer || '',
                        part_number: it.part_number || '',
                        quantity: it.quantity,
                        unit: it.unit || 'шт',
                        specifications: it.specifications || '',
                        comments: it.comments || '',
                        _status: 'unchanged',
                    }))
                });
            } catch (e) {
                console.error(e);
                toast.error('Не удалось загрузить RFQ');
            } finally {
                setLoading(false);
            }
        };
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [rfqId]);

    const addNewItem = () => {
        append({
            line_number: (fields[fields.length - 1]?.line_number || 0) + 1,
            product_type: 'new',
            product_id: undefined,
            product_name: '',
            manufacturer: '',
            part_number: '',
            quantity: 1,
            unit: 'шт',
            specifications: '',
            comments: '',
            _status: 'new',
        });
    };

    const markUpdated = (index: number) => {
        const current = form.getValues(`items.${index}._status`);
        if (!current || current === 'unchanged') form.setValue(`items.${index}._status`, 'updated');
    };

    const addFilesToRow = (rowKey: string, incoming: File[]) => {
        const maxBytes = 50 * 1024 * 1024;
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
                const duplicate = existing.some((e) => e.name === file.name && e.size === file.size && e.lastModified === file.lastModified);
                if (!duplicate) deduped.push(file);
            }
            return { ...prev, [rowKey]: deduped };
        });
    };

    const onFilesChange = (index: number, list: FileList | null) => {
        const key = String(form.getValues(`items.${index}.id`) ?? `new-${index}`);
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

    const onSubmit = async (data: RFQEditFormData) => {
        try {
            setIsSubmitting(true);

            // Сначала обновим шапку RFQ
            const headerPayload: Partial<RFQ> = {
                description: data.description || '',
                priority: data.priority,
                deadline: data.deadline || null,
                delivery_address: data.delivery_address || '',
                payment_terms: data.payment_terms || '',
                delivery_terms: data.delivery_terms || '',
                notes: data.notes || '',
                company: data.company_id,
                contact_person: data.contact_person_id ?? null,
            } as Partial<RFQ>;
            await updateRFQ(rfqId, headerPayload);

            // Затем обработаем строки (create/update/delete)
            const existingIds = new Set((rfq?.items || []).map((i) => i.id));

            for (let i = 0; i < data.items.length; i++) {
                const item = data.items[i];
                // Вычислим line_number заново по порядку в форме
                const lineNumber = i + 1;
                const isExisting = item.id && existingIds.has(item.id);
                const basePayload = {
                    rfq: rfqId,
                    line_number: lineNumber,
                    product: item.product_type === 'existing' ? item.product_id : null,
                    product_name: item.product_name || '',
                    manufacturer: item.manufacturer || '',
                    part_number: item.part_number || '',
                    quantity: item.quantity,
                    unit: item.unit || 'шт',
                    specifications: item.specifications || '',
                    comments: item.comments || '',
                    is_new_product: item.product_type === 'new',
                } as any;

                if (item._status === 'deleted') {
                    if (isExisting) await deleteRFQItem(item.id!);
                    continue;
                }

                if (!isExisting || item._status === 'new') {
                    const created = await createRFQItem(basePayload);
                    const files = filesByRowKey[String(item.id ?? `new-${i}`)] || [];
                    if (files.length > 0) await uploadFilesForRFQItem(created.id, files);
                } else if (item._status === 'updated') {
                    const updated = await updateRFQItem(item.id!, basePayload);
                    const files = filesByRowKey[String(item.id)] || [];
                    if (files.length > 0) await uploadFilesForRFQItem(updated.id, files);
                } else {
                    // Строка без изменений в данных, но пользователь мог добавить файлы
                    const files = filesByRowKey[String(item.id)] || [];
                    if (files.length > 0 && item.id) await uploadFilesForRFQItem(item.id, files);
                }
            }

            toast.success('RFQ успешно обновлён');
            router.push('/dashboard/rfqs');
        } catch (error) {
            console.error('Error updating RFQ:', error);
            toast.error('Ошибка при сохранении RFQ');
        } finally {
            setIsSubmitting(false);
        }
    };

    const removeRow = (index: number) => {
        const current = form.getValues(`items.${index}`);
        if (current?.id) {
            form.setValue(`items.${index}._status`, 'deleted');
        } else {
            remove(index);
        }
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <FormCardSkeleton />
                <DataTableSkeleton columnCount={10} rowCount={5} withPagination={false} />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Основная информация</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid gap-4 md:grid-cols-2">
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
                                            <Textarea placeholder="Подробное описание запроса" className="min-h-[80px]" {...field} />
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
                                            <FormLabel>Компания-заказчик</FormLabel>
                                            <FormControl>
                                                <CompanySelector value={field.value} onValueChange={field.onChange} />
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
                                                <PersonSelector value={field.value ?? undefined} onValueChange={field.onChange} companyId={form.watch('company_id')} />
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
                                                <Input type="datetime-local" value={field.value ?? ''} onChange={(e) => field.onChange(e.target.value || null)} />
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
                                            <Textarea placeholder="Внутренние заметки и комментарии" className="min-h-[60px]" {...field} />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <CardTitle>Строки запроса</CardTitle>
                                <Button type="button" variant="outline" size="sm" onClick={addNewItem} className="gap-2">
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
                                            <TableHead className="w-[50px]" />
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {fields.map((field, index) => {
                                            const productType = form.watch(`items.${index}.product_type`);
                                            const isNewProduct = productType === 'new';
                                            const rowKey = String(form.getValues(`items.${index}.id`) ?? `new-${index}`);
                                            const status = form.watch(`items.${index}._status`);

                                            if (status === 'deleted') return null;

                                            return (
                                                <TableRow key={rowKey}>
                                                    <TableCell className="text-center font-medium">{index + 1}</TableCell>
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
                                                                            markUpdated(index);
                                                                            if (newType === 'new') {
                                                                                form.setValue(`items.${index}.product_id`, undefined);
                                                                                form.setValue(`items.${index}.product_name`, '');
                                                                            } else {
                                                                                form.setValue(`items.${index}.manufacturer`, '');
                                                                                form.setValue(`items.${index}.part_number`, '');
                                                                            }
                                                                        }}
                                                                    />
                                                                    <Label className="text-xs">{field.value === 'existing' ? 'Из базы' : 'Новый'}</Label>
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
                                                                        <Input placeholder="Наименование товара" className="min-w-[180px]" {...field} onChange={(e) => { field.onChange(e); markUpdated(index); }} />
                                                                    )}
                                                                />
                                                                <FormField
                                                                    control={form.control}
                                                                    name={`items.${index}.part_number`}
                                                                    render={({ field }) => (
                                                                        <FormItem>
                                                                            <FormControl>
                                                                                <Input placeholder="Артикул *" className="min-w-[180px]" {...field} onChange={(e) => { field.onChange(e); markUpdated(index); }} />
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
                                                                                onValueChange={(v) => { field.onChange(v); markUpdated(index); }}
                                                                                onProductSelect={(product) => {
                                                                                    if (product) {
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
                                                                        <Input placeholder={isNewProduct ? 'Производитель *' : 'Автозаполнение'} className="min-w-[120px]" disabled={!isNewProduct} {...field} onChange={(e) => { field.onChange(e); markUpdated(index); }} />
                                                                    </FormControl>
                                                                    {isNewProduct && <FormMessage />}
                                                                </FormItem>
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="space-y-2 w-[220px] max-w-[220px]">
                                                            {/* Существующие файлы из бэкенда */}
                                                            {(() => {
                                                                const itemId = form.getValues(`items.${index}.id`);
                                                                const backendFiles = itemId ? (rfq?.items.find((it) => it.id === itemId)?.files || []) : [];
                                                                if (!backendFiles || backendFiles.length === 0) return null;
                                                                return (
                                                                    <ul className="space-y-1 w-full">
                                                                        {backendFiles.map((f) => (
                                                                            <li key={f.id} className="flex items-center gap-2 text-[11px] w-full overflow-hidden">
                                                                                <a href={f.file} target="_blank" rel="noreferrer" className="truncate flex-1 hover:underline" title={f.file}>{f.description || f.file.split('/').pop()}</a>
                                                                                <Button
                                                                                    type="button"
                                                                                    variant="ghost"
                                                                                    size="icon"
                                                                                    className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                                                                                    onClick={async () => {
                                                                                        try {
                                                                                            await deleteRFQItemFile(f.id);
                                                                                            setRfq((prev) => {
                                                                                                if (!prev) return prev;
                                                                                                const nextItems = prev.items.map((it) => (
                                                                                                    it.id === itemId ? { ...it, files: (it.files || []).filter((x) => x.id !== f.id) } : it
                                                                                                ));
                                                                                                return { ...prev, items: nextItems };
                                                                                            });
                                                                                            toast.success('Файл удалён');
                                                                                        } catch (e) {
                                                                                            toast.error('Не удалось удалить файл');
                                                                                        }
                                                                                    }}
                                                                                    aria-label="Удалить файл"
                                                                                >
                                                                                    <IconTrash className="h-3.5 w-3.5" />
                                                                                </Button>
                                                                            </li>
                                                                        ))}
                                                                    </ul>
                                                                );
                                                            })()}
                                                            <input
                                                                ref={(el) => { fileInputsRef.current[rowKey] = el; }}
                                                                type="file"
                                                                multiple
                                                                className="hidden"
                                                                onChange={(e) => onFilesChange(index, e.target.files)}
                                                            />
                                                            <div
                                                                role="button"
                                                                tabIndex={0}
                                                                onClick={() => fileInputsRef.current[rowKey]?.click()}
                                                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputsRef.current[rowKey]?.click(); }}
                                                                onDragOver={(e) => { e.preventDefault(); setDragOverKey(rowKey); }}
                                                                onDragEnter={() => setDragOverKey(rowKey)}
                                                                onDragLeave={() => setDragOverKey((k) => (k === rowKey ? null : k))}
                                                                onDrop={(e) => handleDrop(e as unknown as DragEvent<HTMLDivElement>, rowKey)}
                                                                className={`flex items-center gap-2 justify-start rounded-md border border-dashed p-3 text-xs cursor-pointer transition-colors w-full overflow-hidden ${dragOverKey === rowKey ? 'bg-primary/10 border-primary' : 'hover:bg-muted/50'}`}
                                                            >
                                                                <IconUpload className="h-4 w-4 shrink-0" />
                                                                <span className="truncate min-w-0 flex-1">Перетащите файлы или нажмите, чтобы выбрать</span>
                                                            </div>
                                                            {(filesByRowKey[rowKey]?.length || 0) > 0 && (
                                                                <ul className="space-y-1 w-full">
                                                                    {filesByRowKey[rowKey]!.map((f, fi) => (
                                                                        <li key={`${f.name}-${f.lastModified}`} className="flex items-center gap-2 text-[11px] w-full overflow-hidden">
                                                                            <IconFile className="h-3.5 w-3.5 text-muted-foreground" />
                                                                            <span className="truncate flex-1" title={f.name}>{f.name}</span>
                                                                            <span className="text-muted-foreground">{(f.size / (1024 * 1024)).toFixed(1)} МБ</span>
                                                                            <Button type="button" variant="ghost" size="icon" className="h-6 w-6 p-0" onClick={() => removeFileFromRow(rowKey, fi)} aria-label="Удалить файл">
                                                                                <IconTrash className="h-3.5 w-3.5" />
                                                                            </Button>
                                                                        </li>
                                                                    ))}
                                                                </ul>
                                                            )}
                                                            <div className="text-[10px] text-muted-foreground">до 50 МБ каждый, можно добавить несколько</div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.quantity`}
                                                            render={({ field }) => (
                                                                <FormItem>
                                                                    <FormControl>
                                                                        <Input type="number" min="1" className="min-w-[80px]" {...field} onChange={(e) => { field.onChange(parseInt(e.target.value) || 1); markUpdated(index); }} />
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
                                                                <Select onValueChange={(v) => { field.onChange(v); markUpdated(index); }} defaultValue={field.value}>
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
                                                                <Textarea placeholder="Технические характеристики" className="min-w-[150px] min-h-[60px]" {...field} onChange={(e) => { field.onChange(e); markUpdated(index); }} />
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <FormField
                                                            control={form.control}
                                                            name={`items.${index}.comments`}
                                                            render={({ field }) => (
                                                                <Textarea placeholder="Комментарии" className="min-w-[150px] min-h-[60px]" {...field} onChange={(e) => { field.onChange(e); markUpdated(index); }} />
                                                            )}
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <Button type="button" variant="ghost" size="sm" onClick={() => removeRow(index)} className="h-8 w-8 p-0 text-destructive hover:text-destructive">
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
                                    <div className="text-sm text-muted-foreground mb-2"><span className="text-red-500">*</span> Обязательные поля</div>
                                    <div className="text-xs text-muted-foreground">Всего строк: {fields.length}</div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <div className="flex flex-col sm:flex-row justify-end gap-3 pt-6 border-t">
                        <Button type="button" variant="outline" onClick={() => router.back()} disabled={isSubmitting} className="w-full sm:w-auto">
                            Отмена
                        </Button>
                        <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
                            {isSubmitting ? (<><IconLoader2 className="mr-2 h-4 w-4 animate-spin" />Сохранение...</>) : ('Сохранить изменения')}
                        </Button>
                    </div>
                </form>
            </Form>
        </div>
    );
}


