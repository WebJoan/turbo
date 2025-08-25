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
import { fetchPersonsFromClient } from '@/lib/client-api';
import { PersonListItem } from '@/types/persons';
import { IconLoader2 } from '@tabler/icons-react';

interface PersonSelectorProps {
    value?: number;
    onValueChange: (value?: number) => void;
    companyId?: number;
    placeholder?: string;
}

export function PersonSelector({
    value,
    onValueChange,
    companyId,
    placeholder = "Выберите контактное лицо..."
}: PersonSelectorProps) {
    const [open, setOpen] = useState(false);
    const [persons, setPersons] = useState<PersonListItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState('');

    // Загрузка персон
    useEffect(() => {
        const loadPersons = async () => {
            if (!companyId) {
                setPersons([]);
                return;
            }

            try {
                setLoading(true);
                const result = await fetchPersonsFromClient({
                    page: 1,
                    perPage: 100, // Загружаем больше персон для выбора
                    search: search || undefined
                });

                // Фильтруем персон по выбранной компании
                const filteredPersons = result.items.filter(person => person.company === companyId);
                setPersons(filteredPersons);
            } catch (error) {
                console.error('Error loading persons:', error);
                setPersons([]);
            } finally {
                setLoading(false);
            }
        };

        loadPersons();
    }, [companyId, search]);

    // Сбрасываем выбранную персону если компания изменилась
    useEffect(() => {
        if (value && companyId) {
            const selectedPerson = persons.find(person => person.id === value);
            if (selectedPerson && selectedPerson.company !== companyId) {
                onValueChange(undefined);
            }
        }
    }, [companyId, value, persons, onValueChange]);

    const selectedPerson = useMemo(() => {
        return persons.find((person) => person.id === value);
    }, [persons, value]);

    const handleSelect = (personId: number) => {
        onValueChange(personId === value ? undefined : personId);
        setOpen(false);
    };

    const handleClear = () => {
        onValueChange(undefined);
        setOpen(false);
    };

    if (!companyId) {
        return (
            <Button
                variant="outline"
                disabled
                className="w-full justify-between text-muted-foreground"
            >
                Сначала выберите компанию
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
        );
    }

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className="w-full justify-between"
                >
                    {selectedPerson ? (
                        <div className="flex flex-col items-start">
                            <span className="font-medium">
                                {selectedPerson.last_name} {selectedPerson.first_name} {selectedPerson.middle_name}
                            </span>
                            <div className="text-xs text-muted-foreground">
                                {selectedPerson.position && <span>{selectedPerson.position}</span>}
                                {selectedPerson.email && <span> • {selectedPerson.email}</span>}
                            </div>
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
                            placeholder="Поиск контактных лиц..."
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
                        ) : (
                            <>
                                <CommandGroup>
                                    {selectedPerson && (
                                        <CommandItem
                                            onSelect={handleClear}
                                            className="text-muted-foreground"
                                        >
                                            Очистить выбор
                                        </CommandItem>
                                    )}
                                    {persons.length === 0 ? (
                                        <CommandEmpty>
                                            {search ? 'Контактные лица не найдены' : 'У компании нет контактных лиц'}
                                        </CommandEmpty>
                                    ) : (
                                        persons.map((person) => (
                                            <CommandItem
                                                key={person.id}
                                                onSelect={() => handleSelect(person.id)}
                                                className="flex items-start gap-2"
                                            >
                                                <Check
                                                    className={cn(
                                                        "mr-2 h-4 w-4 mt-1",
                                                        value === person.id ? "opacity-100" : "opacity-0"
                                                    )}
                                                />
                                                <div className="flex flex-col">
                                                    <span className="font-medium">
                                                        {person.last_name} {person.first_name} {person.middle_name}
                                                    </span>
                                                    <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                                                        {person.position && <span>{person.position}</span>}
                                                        {person.department && <span>Отдел: {person.department}</span>}
                                                        {person.email && <span>Email: {person.email}</span>}
                                                        {person.phone && <span>Телефон: {person.phone}</span>}
                                                    </div>
                                                </div>
                                            </CommandItem>
                                        ))
                                    )}
                                </CommandGroup>
                            </>
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}
