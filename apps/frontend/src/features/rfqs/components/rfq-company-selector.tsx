'use client';

import { useState, useEffect, useMemo } from 'react';
import { Check, ChevronsUpDown, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from '@/components/ui/command';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import { fetchCompaniesFromClient, fetchCompanyByIdFromClient } from '@/lib/client-api';
import { CompanyListItem } from '@/types/companies';
import { IconLoader2 } from '@tabler/icons-react';

interface CompanySelectorProps {
    value?: number;
    onValueChange: (value: number) => void;
    placeholder?: string;
}

export function CompanySelector({
    value,
    onValueChange,
    placeholder = "Выберите компанию..."
}: CompanySelectorProps) {
    const [open, setOpen] = useState(false);
    const [companies, setCompanies] = useState<CompanyListItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState('');

    // Загрузка компаний
    useEffect(() => {
        const loadCompanies = async () => {
            try {
                setLoading(true);
                const result = await fetchCompaniesFromClient({
                    page: 1,
                    perPage: 100, // Загружаем больше компаний для выбора
                    search: search || undefined
                });
                // Не теряем выбранную компанию, если её нет в текущей странице
                setCompanies((prev) => {
                    const inPage = result.items;
                    if (value && !inPage.some((c) => c.id === value)) {
                        const existingSelected = prev.find((c) => c.id === value);
                        return existingSelected ? [existingSelected, ...inPage] : inPage;
                    }
                    return inPage;
                });
            } catch (error) {
                console.error('Error loading companies:', error);
            } finally {
                setLoading(false);
            }
        };

        loadCompanies();
    }, [search, value]);

    const selectedCompany = useMemo(() => {
        return companies.find((company) => company.id === value);
    }, [companies, value]);

    // Если значение задано, но компании нет в текущем списке (например, при автозаполнении), подгружаем её
    useEffect(() => {
        const ensureSelectedPresent = async () => {
            if (!value) return;
            const exists = companies.some((c) => c.id === value);
            if (exists) return;
            try {
                const c = await fetchCompanyByIdFromClient(value);
                if (c) setCompanies((prev) => [c, ...prev]);
            } catch (e) {
                // ignore
            }
        };
        ensureSelectedPresent();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [value, companies]);

    const handleSelect = (companyId: number) => {
        onValueChange(companyId);
        setOpen(false);
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className="w-full justify-between"
                >
                    {selectedCompany ? (
                        <div className="flex flex-col items-start">
                            <span className="font-medium">{selectedCompany.name}</span>
                            {selectedCompany.inn && (
                                <span className="text-xs text-muted-foreground">
                                    ИНН: {selectedCompany.inn}
                                </span>
                            )}
                        </div>
                    ) : (
                        <span className="text-muted-foreground">{placeholder}</span>
                    )}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-full p-0" align="start">
                <Command shouldFilter={false}>
                    <div className="flex items-center border-b px-3">
                        <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
                        <input
                            placeholder="Поиск компаний..."
                            className="flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                    <CommandList>
                        {loading ? (
                            <div className="flex items-center justify-center p-6">
                                <IconLoader2 className="h-4 w-4 animate-spin" />
                                <span className="ml-2 text-sm text-muted-foreground">
                                    Загрузка...
                                </span>
                            </div>
                        ) : companies.length === 0 ? (
                            <CommandEmpty>
                                {search ? 'Компании не найдены' : 'Нет доступных компаний'}
                            </CommandEmpty>
                        ) : (
                            <CommandGroup>
                                {companies.map((company) => (
                                    <CommandItem
                                        key={company.id}
                                        onSelect={() => handleSelect(company.id)}
                                        className="flex items-center gap-2"
                                    >
                                        <Check
                                            className={cn(
                                                "mr-2 h-4 w-4",
                                                value === company.id ? "opacity-100" : "opacity-0"
                                            )}
                                        />
                                        <div className="flex flex-col">
                                            <span className="font-medium">{company.name}</span>
                                            <div className="flex gap-2 text-xs text-muted-foreground">
                                                {company.short_name && (
                                                    <span>({company.short_name})</span>
                                                )}
                                                {company.inn && <span>ИНН: {company.inn}</span>}
                                            </div>
                                        </div>
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}
