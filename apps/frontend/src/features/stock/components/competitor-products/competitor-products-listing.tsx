import { searchParamsCache } from '@/lib/searchparams';
import { CompetitorProductsTable } from './competitor-products-table';
import { fetchCompetitorProducts } from '@/lib/stock';

type CompetitorProductsListingPage = {
    searchParams?: Record<string, string | string[] | undefined>;
};

export default async function CompetitorProductsListingPage({
    searchParams
}: CompetitorProductsListingPage) {
    const { page, name, perPage: pageLimit } = searchParamsCache.parse(searchParams || {});
    const search = name ?? undefined;

    const res = await fetchCompetitorProducts({
        page,
        page_size: pageLimit,
        part_number: search,
    });

    return (
        <CompetitorProductsTable
            data={res.items}
            totalItems={res.total}
        />
    );
}
