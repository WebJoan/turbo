import { searchParamsCache } from '@/lib/searchparams';
import { fetchPersonsFromBackend } from '@/lib/persons-server';
import { PersonTable } from './person-tables';
import { personColumns } from './person-tables/columns';
import { PersonListItem } from '@/types/persons';

type PersonListingPage = { searchParams?: Record<string, string | string[] | undefined> };

export default async function PersonListingPage({ searchParams }: PersonListingPage) {
    const { page, name: search, perPage: pageLimit } = searchParamsCache.parse(searchParams || {});

    const res = await fetchPersonsFromBackend({ page, perPage: pageLimit, search });
    const persons: PersonListItem[] = res.items;
    const totalPersons: number = res.total;

    return (
        <PersonTable data={persons} totalItems={totalPersons} columns={personColumns} />
    );
}


