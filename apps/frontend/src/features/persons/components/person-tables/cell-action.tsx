'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreHorizontal, Edit } from 'lucide-react';
import { PersonListItem } from '@/types/persons';

interface PersonCellActionProps {
    data: PersonListItem;
}

export function PersonCellAction({ data }: PersonCellActionProps) {
    const router = useRouter();

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-8 w-8 p-0">
                    <span className="sr-only">Открыть меню</span>
                    <MoreHorizontal className="h-4 w-4" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                <DropdownMenuLabel>Действия</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => router.push(`/dashboard/customers/persons/${data.id}/edit`)}>
                    <Edit className="mr-2 h-4 w-4" />
                    Редактировать
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}


