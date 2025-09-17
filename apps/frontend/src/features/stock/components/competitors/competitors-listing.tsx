import { searchParamsCache } from '@/lib/searchparams';
import { CompetitorsTable } from './competitors-table';
import { fetchCompetitors } from '@/lib/stock';
import { Competitor } from '@/types/stock';

type CompetitorsListingPage = {
    searchParams?: Record<string, string | string[] | undefined>;
};

export default async function CompetitorsListingPage({ searchParams }: CompetitorsListingPage) {
    const { page, name, perPage: pageLimit } = searchParamsCache.parse(searchParams || {});
    const search = name ?? undefined;

    const res = await fetchCompetitors({
        page,
        page_size: pageLimit,
        name_contains: search,
    });

    return (
        <CompetitorsTable
            data={res.items}
            totalItems={res.total}
        />
    );
}
