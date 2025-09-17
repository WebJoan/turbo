'use server';

import { searchParamsCache } from '@/lib/searchparams';
import { fetchProductsFromBackend } from '@/lib/products';
import { fetchCompetitors, fetchOurPriceHistory, fetchPriceComparison } from '@/lib/stock';
import { Competitor } from '@/types/stock';
import PriceComparisonTable, { PriceComparisonRow } from './price-comparison-table';

type PriceComparisonListingPage = { searchParams?: Record<string, string | string[] | undefined> };

export default async function PriceComparisonListing({ searchParams }: PriceComparisonListingPage) {
    const { page, name: search, perPage: pageLimit } = searchParamsCache.parse(searchParams || {});

    const [{ items: products, total }, competitorsRes] = await Promise.all([
        fetchProductsFromBackend({ page, perPage: pageLimit, search }),
        fetchCompetitors({ page: 1, page_size: 100 }).catch(() => ({ items: [], total: 0 }))
    ]);

    const competitors: Competitor[] = competitorsRes.items;

    const rows: PriceComparisonRow[] = await Promise.all(
        products.map(async (p) => {
            const [ourHist, comparison] = await Promise.all([
                fetchOurPriceHistory({ product_id: p.id, page: 1, page_size: 1 }).catch(() => ({ items: [], total: 0 })),
                fetchPriceComparison(p.id).catch(() => null)
            ]);

            const our_price = ourHist.items[0]?.price_ex_vat ?? null;
            const competitorMap: PriceComparisonRow['competitorMap'] = {};

            if (comparison) {
                for (const snap of comparison.competitor_prices) {
                    competitorMap[snap.competitor.id] = {
                        price: snap.price_ex_vat,
                        currency: snap.currency,
                        stock_qty: snap.stock_qty
                    };
                }
            }

            return {
                id: p.id,
                ext_id: p.ext_id,
                name: p.name,
                brand_name: p.brand_name,
                our_price,
                competitorMap
            } satisfies PriceComparisonRow;
        })
    );

    return (
        <PriceComparisonTable data={rows} totalItems={total} competitors={competitors} />
    );
}


