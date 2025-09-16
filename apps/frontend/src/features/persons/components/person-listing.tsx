import { searchParamsCache } from '@/lib/searchparams';
import { fetchPersonsFromBackend } from '@/lib/persons-server';
import { PersonTable } from './person-tables';
import { personColumns } from './person-tables/columns';
import { PersonListItem } from '@/types/persons';

type PersonListingPage = {};

export default async function PersonListingPage({ }: PersonListingPage) {
    const page = searchParamsCache.get('page');
    const search = searchParamsCache.get('name');
    const pageLimit = searchParamsCache.get('perPage');

    const res = await fetchPersonsFromBackend({ page, perPage: pageLimit, search });
    const persons: PersonListItem[] = res.items;
    const totalPersons: number = res.total;

    return (
        <PersonTable data={persons} totalItems={totalPersons} columns={personColumns} />
    );
}


