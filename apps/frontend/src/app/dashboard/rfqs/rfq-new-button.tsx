'use client';

import { buttonVariants } from '@/components/ui/button';
import { useAuth } from '@/lib/use-auth';
import { cn } from '@/lib/utils';
import { IconPlus } from '@tabler/icons-react';
import Link from 'next/link';

export function NewRFQButton() {
    const { user, loading } = useAuth();
    if (loading || user?.role !== 'sales') return null;
    return (
        <Link href='/dashboard/rfqs/new' className={cn(buttonVariants(), 'text-xs md:text-sm')}>
            <IconPlus className='mr-2 h-4 w-4' /> Новый RFQ
        </Link>
    );
}


