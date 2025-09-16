'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

import { CompanySelector } from '@/features/rfqs/components';
import { createPerson } from '@/lib/persons';
import { PersonCreateInput, PersonStatus } from '@/types/persons';

const personSchema = z.object({
    company: z.number({ required_error: 'Выберите компанию' }).min(1, 'Выберите компанию'),
    last_name: z.string().min(1, 'Укажите фамилию'),
    first_name: z.string().min(1, 'Укажите имя'),
    middle_name: z.string().optional(),
    email: z.string().email('Некорректный email'),
    phone: z.string().optional(),
    position: z.string().optional(),
    department: z.string().optional(),
    status: z.enum(['active', 'inactive', 'suspended'] as [PersonStatus, ...PersonStatus[]]).default('active'),
    is_primary_contact: z.boolean().default(false),
    notes: z.string().optional(),
});

type PersonFormData = z.infer<typeof personSchema>;

const statusOptions: { value: PersonStatus; label: string }[] = [
    { value: 'active', label: 'Активный' },
    { value: 'inactive', label: 'Неактивный' },
    { value: 'suspended', label: 'Приостановлен' },
];

export function PersonCreateForm() {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);

    const form = useForm<PersonFormData>({
        resolver: zodResolver(personSchema),
        defaultValues: {
            company: undefined as unknown as number,
            last_name: '',
            first_name: '',
            middle_name: '',
            email: '',
            phone: '',
            position: '',
            department: '',
            status: 'active',
            is_primary_contact: false,
            notes: '',
        },
    });

    const onSubmit = async (data: PersonFormData) => {
        try {
            setIsSubmitting(true);
            const payload: PersonCreateInput = {
                company: data.company,
                last_name: data.last_name,
                first_name: data.first_name,
                middle_name: data.middle_name || null,
                email: data.email,
                phone: data.phone || null,
                position: data.position || null,
                department: data.department || null,
                status: data.status,
                is_primary_contact: data.is_primary_contact,
                notes: data.notes || null,
            };
            await createPerson(payload);
            toast.success('Персона успешно создана');
            router.push('/dashboard/customers/persons');
        } catch (e) {
            console.error(e);
            toast.error('Ошибка при создании персоны');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                <div className="grid gap-4 md:grid-cols-2">
                    <FormField
                        control={form.control}
                        name="company"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Компания</FormLabel>
                                <FormControl>
                                    <CompanySelector value={field.value} onValueChange={field.onChange} placeholder="Выберите компанию..." />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="email"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Email</FormLabel>
                                <FormControl>
                                    <Input type="email" placeholder="name@company.com" {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                    <FormField
                        control={form.control}
                        name="last_name"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Фамилия</FormLabel>
                                <FormControl>
                                    <Input placeholder="Иванов" {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="first_name"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Имя</FormLabel>
                                <FormControl>
                                    <Input placeholder="Иван" {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="middle_name"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Отчество</FormLabel>
                                <FormControl>
                                    <Input placeholder="Иванович" {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                    <FormField
                        control={form.control}
                        name="phone"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Телефон</FormLabel>
                                <FormControl>
                                    <Input placeholder="+7..." {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="position"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Должность</FormLabel>
                                <FormControl>
                                    <Input placeholder="Менеджер" {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="department"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Отдел</FormLabel>
                                <FormControl>
                                    <Input placeholder="Продажи" {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                    <FormField
                        control={form.control}
                        name="status"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Статус</FormLabel>
                                <Select value={field.value} onValueChange={field.onChange}>
                                    <FormControl>
                                        <SelectTrigger>
                                            <SelectValue placeholder="Выберите статус" />
                                        </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                        {statusOptions.map((s) => (
                                            <SelectItem key={s.value} value={s.value}>
                                                {s.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="is_primary_contact"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Основной контакт</FormLabel>
                                <div className="flex items-center gap-3">
                                    <Switch checked={field.value} onCheckedChange={field.onChange} id="is_primary_contact" />
                                    <Label htmlFor="is_primary_contact">Да</Label>
                                </div>
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
                                <Textarea rows={4} placeholder="Дополнительная информация" {...field} />
                            </FormControl>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <div className="flex justify-end">
                    <Button type="submit" disabled={isSubmitting}>
                        {isSubmitting ? 'Сохранение...' : 'Создать персону'}
                    </Button>
                </div>
            </form>
        </Form>
    );
}


